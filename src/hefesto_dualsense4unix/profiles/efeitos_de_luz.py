"""Os efeitos da barra de luz como funções puras do tempo (A-LUZ-ANIMADA-GANHA-A-LISTA-BOA).

Nada aqui lê relógio, arquivo ou estado: a mesma entrada dá a mesma saída; o laço do daemon
(``daemon/subsystems/luz_animada.py``) só escolhe o instante. Todo efeito modula o BRILHO da cor
do controle (só o arco-íris gira o matiz, e a Maré o desloca até 30 graus). Nenhuma subida passa
de 3 por segundo (WCAG 2.3.1), sempre em transição suave; o brilho
tem piso, e o vermelho saturado nunca alterna com o apagado. O ritmo 10 é o mais rápido que a
regra deixa: o valor da tabela da sprint é o dele, e os ritmos menores o alongam.
"""
from __future__ import annotations

import colorsys
import math
import random
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.profiles.estilos_de_jogo import DISTANCIA_MINIMA
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DA_MAO_DA_LUZ,
    BASES_DE_AMBIENTE_DA_LUZ,
    BASES_DO_SOM_DA_LUZ,
    EfeitoDaLuz,
)

RGB = tuple[int, int, int]

#: O fundo do respirar: a barra nunca apaga de todo, só abaixa.
PISO_DO_RESPIRAR = 0.08
#: O fundo do piscar: o vermelho saturado nunca alterna com o apagado.
PISO_DO_PISCAR = 0.15
#: O fundo da batida do coração.
PISO_DA_BATIDA = 0.25
#: A borda do piscar: a luz leva isto para subir ou descer (a onda quadrada tinha zero).
BORDA_DO_PISCAR_S = 0.150
#: Teto do piscar, em lampejos por segundo (WCAG 2.3.1).
TETO_DO_PISCAR_HZ = 3.0
PISO_DO_PISCAR_HZ = 0.3
#: O fundo da Onda: a barra nunca apaga de todo enquanto a crista não chega.
PISO_DA_ONDA = 0.20
#: Os LEDs de número do jogador, de um lado ao outro: a crista da Onda corre por eles e a barra
#: acompanha o do meio.
LEDS_DA_ONDA = 5
LED_DO_MEIO_DA_ONDA = LEDS_DA_ONDA // 2
#: A meia-largura da crista, em LEDs: ela acende o LED que passa e esmaece nos vizinhos.
MEIA_LARGURA_DA_ONDA = 1.5
#: A luzinha do jogador é liga/desliga: acende quando a crista a leva acima do meio do passeio.
LIMIAR_DA_LUZINHA_DA_ONDA = 0.5
#: O fundo do Relâmpago: o clarão nunca vem do apagado (nem o vermelho alterna com o preto).
PISO_DO_RELAMPAGO = 0.20
#: O clarão sobe em cosseno e desce mais devagar; o eco vem logo depois, mais fraco. Duas subidas
#: por rajada, e a rajada mais curta dura 1,4 s: nunca passa de 3 subidas por segundo (WCAG 2.3.1).
SUBIDA_DO_RELAMPAGO_S = 0.12
DESCIDA_DO_RELAMPAGO_S = 0.30
ECO_DO_RELAMPAGO_S = 0.50
FORCA_DO_ECO = 0.7
DESCIDA_DO_ECO_S = 0.25
#: A chama passeia entre estes dois brilhos.
PISO_DA_CHAMA = 0.6
TETO_DA_CHAMA = 1.0
#: A Maré desloca o matiz até 30 graus.
DESLOCAMENTO_DA_MARE = 30.0 / 360.0
#: Uma volta do arco-íris dura no mínimo isto.
VOLTA_MINIMA_DO_ARCO_IRIS_S = 8.0
#: Defasagem do arco-íris entre dois controles vizinhos: um quarto de volta.
DEFASAGEM_DO_ARCO_IRIS = 0.25
#: O Acende da Corrida (20/10/2026): a barra segue o curso do gatilho, do piso à cor cheia, e o
#: brilho nunca anda mais depressa que três vaivéns (subir e descer) por segundo.
PISO_DO_ACENDE = 0.25
VAIVENS_DO_ACENDE_POR_S = 3.0
TETO_DO_ACENDE_POR_S = 2.0 * (1.0 - PISO_DO_ACENDE) * VAIVENS_DO_ACENDE_POR_S
MEIO_VAIVEM_DO_ACENDE_S = 1.0 / (2.0 * VAIVENS_DO_ACENDE_POR_S)
#: A Bateria da Maratona: abaixo disto, fora da carga, a barra respira (5 s por respiração, o
#: ritmo 2) e nunca pisca; acima, segue fixa.
LIMIAR_DE_BATERIA_PCT = 30
RITMO_DA_BATERIA = 2
ESTADOS_DE_CARGA_EM_DIA = frozenset({"carregando", "cheio"})
#: Os efeitos cujo desenho é ENTRE os controles (a defasagem do arco-íris, o mesmo ângulo da
#: Maré): o laço os conta num relógio só, o da mesa, e não do instante em que cada um entrou.
BASES_DO_RELOGIO_COMUM = frozenset(
    {"arco-iris", "mare", "aurora", "respira-em-cores"})  # (noqa-acento) chave ASCII

#: Os efeitos que leem um dado vivo ou guardam estado (a mão, o som, a carga, o calor e o acaso das
#: Estrelas: 22/10/2026): têm estado por controle e por isso não são função só do tempo. A Aurora
#: é função só do tempo e fica de fora.
BASES_DE_DADO_VIVO = frozenset(
    BASES_DA_MAO_DA_LUZ + BASES_DO_SOM_DA_LUZ
    + tuple(b for b in BASES_DE_AMBIENTE_DA_LUZ if b != "aurora") + ("ondulacao",))
#: Os efeitos que pintam também as luzinhas do jogador: o quadro leva barra e luzinhas juntas.
BASES_COM_LUZINHAS = frozenset({"estrelas", "onda", "ondulacao", "vaivem", "enche"})
#: A cor do símbolo apertado no «Reage ao botão» (△ verde, ○ vermelho, ✕ azul, □ rosa).
COR_DO_TRIANGULO: RGB = (0, 255, 0)
COR_DO_CIRCULO: RGB = (255, 0, 0)
COR_DO_XIS: RGB = (0, 0, 255)
COR_DO_QUADRADO: RGB = (255, 105, 180)
CORES_DOS_SIMBOLOS: Mapping[str, RGB] = {
    "triangle": COR_DO_TRIANGULO,
    "circle": COR_DO_CIRCULO,
    "cross": COR_DO_XIS,
    "square": COR_DO_QUADRADO,
}
#: O fundo do «Reage ao botão»: sem aperto a barra fica na cor escolhida, nunca apaga.
PISO_DO_REAGE = PISO_DO_ACENDE
#: O clarão do aperto sobe em meio cosseno nisto e desce devagar (de 2 s no ritmo 1 a 0,5 s no 10).
SUBIDA_DO_REAGE_S = 0.12
#: No máximo isto de subidas em qualquer janela de 1 s (WCAG 2.3.1): aperto a mais NÃO sobe.
SUBIDAS_DO_REAGE_POR_S = 3
#: A roda de cores não gira mais depressa que isto, em voltas por segundo: uma volta inteira passa
#: por duas luminâncias altas (verde e ciano/amarelo), então 1 volta/s fica abaixo dos 3 clarões.
VOLTAS_DO_MATIZ_POR_S = 1.0
#: A inclinação com menos que isto de gravidade (em g) é leitura solta, não direção: ignora.
GRAVIDADE_MINIMA_G = 0.3
#: O controle deitado (a gravidade toda no eixo y) não tem lado para baixo: com menos que isto da
#: gravidade no plano x-z (~10 graus de inclinação), a cor fica onde está em vez de seguir o ruído.
INCLINACAO_MINIMA_G = 0.17
#: O toque cobre o matiz de 0 a 300 graus (do vermelho ao magenta): a ponta direita não volta
#: ao vermelho da esquerda.
VOLTA_DO_TOQUE = 300.0 / 360.0

_RITMO_MAXIMO = 10


def _inteiro(valor: float) -> int:
    return max(0, min(255, round(valor)))


def _escalar(cor: RGB, fator: float) -> RGB:
    return (_inteiro(cor[0] * fator), _inteiro(cor[1] * fator), _inteiro(cor[2] * fator))


def _entre_ritmos(ritmo: int, no_mais_lento: float, no_mais_rapido: float) -> float:
    """Interpola em linha reta do ritmo 1 (o mais lento) ao ritmo 10 (o mais rápido)."""
    passo = (max(1, min(_RITMO_MAXIMO, ritmo)) - 1) / (_RITMO_MAXIMO - 1)
    return no_mais_lento + (no_mais_rapido - no_mais_lento) * passo


def _suave(u: float) -> float:
    """Meio cosseno de 0 a 1: a subida e a descida sem quina."""
    u = max(0.0, min(1.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def periodo_do_respirar_s(ritmo: int) -> float:
    """Uma respiração inteira: de 10 s no ritmo 1 a 1 s no ritmo 10."""
    return 10.0 / max(1, ritmo)


def frequencia_do_piscar_hz(ritmo: int) -> float:
    """Lampejos por segundo: de 0,3 Hz no ritmo 1 a 3 Hz no ritmo 10, nunca acima do teto."""
    hz = PISO_DO_PISCAR_HZ + (max(1, ritmo) - 1) * 0.3
    return min(TETO_DO_PISCAR_HZ, hz)


def periodo_do_arco_iris_s(ritmo: int) -> float:
    """Uma volta inteira no círculo de cores: de 20 s no ritmo 1 a 8 s no ritmo 10."""
    return max(VOLTA_MINIMA_DO_ARCO_IRIS_S, _entre_ritmos(ritmo, 20.0, VOLTA_MINIMA_DO_ARCO_IRIS_S))


def periodo_da_batida_s(ritmo: int) -> float:
    """Um batimento: de 2,5 s no ritmo 1 a 1,0 s no ritmo 10."""
    return _entre_ritmos(ritmo, 2.5, 1.0)


def troca_da_chama_s(ritmo: int) -> float:
    """De quanto em quanto tempo a chama escolhe outro alvo: de 3 s no ritmo 1 a 1 s no 10."""
    return _entre_ritmos(ritmo, 3.0, 1.0)


def periodo_da_mare_s(ritmo: int) -> float:
    """Ida e volta do matiz: de 16 s no ritmo 1 a 8 s no ritmo 10."""
    return _entre_ritmos(ritmo, 16.0, 8.0)


def periodo_da_onda_s(ritmo: int) -> float:
    """Uma passada da crista pelos cinco LEDs: de 6 s no ritmo 1 a 1,5 s no ritmo 10."""
    return _entre_ritmos(ritmo, 6.0, 1.5)


def periodo_do_relampago_s(ritmo: int) -> float:
    """De um clarão ao seguinte: de 7 s no ritmo 1 a 1,4 s no ritmo 10."""
    return _entre_ritmos(ritmo, 7.0, 1.4)


def brilho_do_respirar(t: float, periodo_s: float) -> float:
    """Cosseno de piso 0,08: o fundo em ``t = 0`` e o topo no meio do período."""
    fase = (t / periodo_s) % 1.0
    return PISO_DO_RESPIRAR + (1.0 - PISO_DO_RESPIRAR) * (0.5 - 0.5 * math.cos(2 * math.pi * fase))


def brilho_do_piscar(t: float, hz: float) -> float:
    """O lampejo com borda suave: cheio, desce em 150 ms, fica no piso 0,15 e sobe em 150 ms.

    Metade do ciclo fica no alto e metade no baixo; a borda é de 150 ms, ou de meio ciclo
    quando 150 ms não cabem (no teto de 3 Hz sobram 17 ms de alto e de baixo).
    """
    periodo = 1.0 / hz
    borda = min(BORDA_DO_PISCAR_S, periodo / 2)
    x = t % periodo
    meio = periodo / 2
    if x < meio - borda:
        return 1.0
    if x < meio:
        return 1.0 - (1.0 - PISO_DO_PISCAR) * _suave((x - (meio - borda)) / borda)
    if x < periodo - borda:
        return PISO_DO_PISCAR
    return PISO_DO_PISCAR + (1.0 - PISO_DO_PISCAR) * _suave((x - (periodo - borda)) / borda)


def _lombada(x: float, centro: float, meia_largura: float) -> float:
    """Uma subida e uma descida em cosseno, de 0 a 1, só dentro da meia-largura."""
    distancia = abs(x - centro)
    if distancia >= meia_largura:
        return 0.0
    return 0.5 + 0.5 * math.cos(math.pi * distancia / meia_largura)


def brilho_da_batida(t: float, periodo_s: float) -> float:
    """Duas subidas rápidas e uma pausa, como o coração; piso 0,25."""
    x = (t / periodo_s) % 1.0
    pico = max(_lombada(x, 0.10, 0.10), 0.8 * _lombada(x, 0.34, 0.10))
    return PISO_DA_BATIDA + (1.0 - PISO_DA_BATIDA) * pico


def brilho_da_onda(t: float, periodo_s: float, led: int = LED_DO_MEIO_DA_ONDA) -> float:
    """O brilho do LED ``led`` (0 a 4) quando a crista corre da ponta 0 à ponta 4 em ``periodo_s``.

    A crista entra pela esquerda, atravessa os cinco LEDs e sai pela direita; o fundo é
    ``PISO_DA_ONDA``. A barra acompanha o LED do meio (o padrão): uma subida por passada.
    """
    fase = (t / periodo_s) % 1.0
    curso = LEDS_DA_ONDA - 1 + 2 * MEIA_LARGURA_DA_ONDA
    crista = -MEIA_LARGURA_DA_ONDA + fase * curso
    return PISO_DA_ONDA + (1.0 - PISO_DA_ONDA) * _lombada(led, crista, MEIA_LARGURA_DA_ONDA)


def brilhos_da_onda(t: float, periodo_s: float) -> tuple[float, ...]:
    """O brilho de cada um dos cinco LEDs do jogador no instante ``t``, da esquerda à direita."""
    return tuple(brilho_da_onda(t, periodo_s, led) for led in range(LEDS_DA_ONDA))


def luzinhas_da_onda(
    t: float, periodo_s: float
) -> tuple[bool, bool, bool, bool, bool] | None:
    """As cinco luzinhas do jogador no instante ``t``: acesa a que a crista leva acima do limiar.

    Entre uma passada e outra a crista está fora dos cinco LEDs e nenhuma acende: aí vale o número
    do jogador (``None``), junto com a barra no piso. Cada luzinha acende no máximo duas vezes por
    passada (a crista e a volta do número), e a passada mais curta é de 1,5 s.
    """
    return _luzinhas_pelo_limiar(brilhos_da_onda(t, periodo_s))


def _luzinhas_pelo_limiar(brilhos: Sequence[float]) -> tuple[bool, bool, bool, bool, bool] | None:
    """Acesa a luzinha cuja crista passa do meio do passeio; nenhuma acesa é o número (``None``)."""
    corte = PISO_DA_ONDA + (1.0 - PISO_DA_ONDA) * LIMIAR_DA_LUZINHA_DA_ONDA
    a, b, c, d, e = (brilho >= corte for brilho in brilhos)
    acesas = (a, b, c, d, e)
    return acesas if any(acesas) else None


def periodo_do_vaivem_s(ritmo: int) -> float:
    """Uma ida e volta da crista pelas luzinhas: de 8 s no ritmo 1 a 2 s no ritmo 10."""
    return _entre_ritmos(ritmo, 8.0, 2.0)


def crista_do_vaivem(t: float, periodo_s: float) -> float:
    """Onde a crista do Vaivém está: sai de fora da luzinha 0, chega à 4 e volta para fora.

    Fora da luzinha 0 nenhuma acende, e é aí, entre uma ida e volta e a seguinte, que o número do
    jogador volta, pela regra da Onda.
    """
    fase = (t / periodo_s) % 1.0
    ida = 1.0 - abs(2.0 * fase - 1.0)
    return -MEIA_LARGURA_DA_ONDA + ida * (LEDS_DA_ONDA - 1 + MEIA_LARGURA_DA_ONDA)


def brilhos_do_vaivem(t: float, periodo_s: float) -> tuple[float, ...]:
    """O brilho de cada luzinha no Vaivém, com a lombada e o piso da Onda."""
    crista = crista_do_vaivem(t, periodo_s)
    return tuple(PISO_DA_ONDA + (1.0 - PISO_DA_ONDA) * _lombada(led, crista, MEIA_LARGURA_DA_ONDA)
                 for led in range(LEDS_DA_ONDA))


def brilho_do_vaivem(t: float, periodo_s: float) -> float:
    """A barra do Vaivém: a crista no LED do meio, duas subidas por ida e volta."""
    return brilhos_do_vaivem(t, periodo_s)[LED_DO_MEIO_DA_ONDA]


#: O Enche: as luzinhas acendem uma por passo (cinco passos), as cinco ficam um passo e o número
#: volta um passo. Uma subida da barra e de cada luzinha por ciclo.
PASSOS_DO_ENCHE = LEDS_DA_ONDA + 2


def passo_do_enche_s(ritmo: int) -> float:
    """Um passo do Enche: de 1,2 s no ritmo 1 a 0,4 s no ritmo 10 (o ciclo de sete, 2,8 s)."""
    return _entre_ritmos(ritmo, 1.2, 0.4)


def luzinhas_do_enche(t: float, passo_s: float) -> tuple[bool, bool, bool, bool, bool] | None:
    """As luzinhas do Enche em ``t``: da 0 à 4, uma por passo; no último passo, o número."""
    passo = int(t / passo_s) % PASSOS_DO_ENCHE
    if passo == PASSOS_DO_ENCHE - 1:
        return None
    acesas = min(passo + 1, LEDS_DA_ONDA)
    a, b, c, d, e = (led < acesas for led in range(LEDS_DA_ONDA))
    return (a, b, c, d, e)


def brilho_do_enche(t: float, passo_s: float) -> float:
    """A barra do Enche: sobe do piso ao cheio com as acesas e desce no passo do número.

    De um nível ao seguinte em meio cosseno dentro do passo, em degraus de 1/16; função só do tempo.
    """
    corrido = t / passo_s
    passo = int(corrido) % PASSOS_DO_ENCHE
    u = _suave(corrido - math.floor(corrido))

    def nivel(acesas: int) -> float:
        return PISO_DA_ONDA + (1.0 - PISO_DA_ONDA) * acesas / LEDS_DA_ONDA

    if passo < LEDS_DA_ONDA:
        brilho = nivel(passo) + (nivel(passo + 1) - nivel(passo)) * u
    elif passo == LEDS_DA_ONDA:
        brilho = 1.0
    else:
        brilho = 1.0 - (1.0 - PISO_DA_ONDA) * u
    # Em degraus, como a barra das Estrelas: não gasta um report a cada tique.
    em_degraus = round(brilho * DEGRAUS_DA_BARRA_DAS_ESTRELAS) / DEGRAUS_DA_BARRA_DAS_ESTRELAS
    return max(PISO_DA_ONDA, min(1.0, em_degraus))


def luzinhas_no_instante(
    efeito: EfeitoDaLuz, t: float
) -> tuple[bool, bool, bool, bool, bool] | None:
    """As luzinhas de um efeito que é função só do tempo; ``None`` é o número do jogador."""
    if efeito.base == "onda":
        return luzinhas_da_onda(t, periodo_da_onda_s(efeito.ritmo))
    if efeito.base == "vaivem":
        return _luzinhas_pelo_limiar(brilhos_do_vaivem(t, periodo_do_vaivem_s(efeito.ritmo)))
    if efeito.base == "enche":
        return luzinhas_do_enche(t, passo_do_enche_s(efeito.ritmo))
    return None


def _clarao(x: float, subida_s: float, descida_s: float) -> float:
    """Um clarão de 0 a 1: sobe em cosseno em ``subida_s`` e desce em ``descida_s``; zero fora."""
    if x < 0.0 or x >= subida_s + descida_s:
        return 0.0
    if x < subida_s:
        return _suave(x / subida_s)
    return 1.0 - _suave((x - subida_s) / descida_s)


def brilho_do_relampago(t: float, periodo_s: float) -> float:
    """O clarão e o seu eco, de borda suave, sobre o piso 0,20; depois o escuro até a próxima.

    Duas subidas por rajada (o clarão e, ``ECO_DO_RELAMPAGO_S`` depois, um eco a 70%). É o estrobo
    dentro da regra da casa: nunca vai ao preto e nunca passa de 3 subidas por segundo.
    """
    x = t % periodo_s
    pico = max(
        _clarao(x, SUBIDA_DO_RELAMPAGO_S, DESCIDA_DO_RELAMPAGO_S),
        FORCA_DO_ECO * _clarao(x - ECO_DO_RELAMPAGO_S, SUBIDA_DO_RELAMPAGO_S, DESCIDA_DO_ECO_S),
    )
    return PISO_DO_RELAMPAGO + (1.0 - PISO_DO_RELAMPAGO) * pico


_MASCARA_64 = (1 << 64) - 1


def _sorteio(semente: int, k: int) -> float:
    """Um número em [0, 1) que só depende da semente e de ``k`` (splitmix64, sem estado)."""
    z = (semente + (k + 1) * 0x9E3779B97F4A7C15) & _MASCARA_64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASCARA_64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASCARA_64
    z ^= z >> 31
    return z / float(1 << 64)


def _alvo_da_chama(semente: int, k: int) -> float:
    return PISO_DA_CHAMA + (TETO_DA_CHAMA - PISO_DA_CHAMA) * _sorteio(semente, k)


def brilho_da_chama(t: float, troca_s: float, semente: int) -> float:
    """O passeio suave entre 0,6 e 1,0: a cada ``troca_s`` há um alvo novo e o brilho vai até ele.

    Os alvos vêm de ``semente`` (um por controle): a mesma entrada dá a mesma saída.
    """
    k = math.floor(t / troca_s)
    u = (t - k * troca_s) / troca_s
    de, para = _alvo_da_chama(semente, k), _alvo_da_chama(semente, k + 1)
    return de + (para - de) * _suave(u)


def deslocamento_da_mare(t: float, periodo_s: float) -> float:
    """O quanto do círculo de matiz a cor andou: de 0 a 30 graus e de volta, em cosseno."""
    return DESLOCAMENTO_DA_MARE * (0.5 - 0.5 * math.cos(2 * math.pi * t / periodo_s))


def _com_o_matiz_andado(cor: RGB, fracao: float) -> RGB:
    h, s, v = colorsys.rgb_to_hsv(cor[0] / 255, cor[1] / 255, cor[2] / 255)
    r, g, b = colorsys.hsv_to_rgb((h + fracao) % 1.0, s, v)
    return (_inteiro(r * 255), _inteiro(g * 255), _inteiro(b * 255))


def _distancia(a: RGB, b: RGB) -> int:
    """|ΔR| + |ΔG| + |ΔB|, a mesma conta de ``estilos_de_jogo`` para a distância mínima."""
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def amplitude_da_mare(cores: Sequence[RGB]) -> float:
    """A fração dos 30 graus que a Maré pode andar sem aproximar dois controles demais.

    ``cores`` são as cores-base dos controles que tocam Maré juntos; todos andam o mesmo ângulo
    ao mesmo tempo. Sobe-se de grau em grau e para no último em que o par mais próximo ainda
    está a ``min(DISTANCIA_MINIMA, o que já estava)``. Um controle só (ou nenhum par) anda tudo.
    """
    if len(cores) < 2:
        return 1.0
    pares = [(a, b) for i, a in enumerate(cores) for b in cores[i + 1:]]
    chao = min(DISTANCIA_MINIMA, min(_distancia(a, b) for a, b in pares))
    graus = round(DESLOCAMENTO_DA_MARE * 360)
    for grau in range(1, graus + 1):
        andado = grau / 360.0
        if min(
            _distancia(_com_o_matiz_andado(a, andado), _com_o_matiz_andado(b, andado))
            for a, b in pares
        ) < chao:
            return (grau - 1) / graus
    return 1.0


def brilho_do_acende(curso: float) -> float:
    """O brilho da barra para um curso do gatilho de 0 a 1: do piso à cor cheia."""
    return PISO_DO_ACENDE + (1.0 - PISO_DO_ACENDE) * max(0.0, min(1.0, curso))


class BrilhoDoAcende:
    """O brilho do Acende de UM controle, com o teto de três vaivéns por segundo.

    Dois freios, e os dois são precisos: o brilho anda no máximo ``TETO_DO_ACENDE_POR_S`` por
    segundo, e só VIRA de sentido (de subir para descer, ou o contrário) depois de meio vaivém.
    Sem o segundo, um dedo que bate o gatilho a cada tique faria o brilho tremer pequeno e
    rápido, dezenas de vezes por segundo, e o teto de brilho por segundo não o seguraria.
    """

    def __init__(self, curso: float = 0.0) -> None:
        self.brilho = brilho_do_acende(curso)
        self._sentido = 0
        self._virou_em = float("-inf")
        self._visto_em: float | None = None

    def andar(self, curso: float, agora: float) -> float:
        """O brilho de agora, a caminho do alvo do curso (0 a 1)."""
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        alvo = brilho_do_acende(curso)
        sentido = (alvo > self.brilho) - (alvo < self.brilho)
        if sentido == 0:
            return self.brilho
        if sentido != self._sentido:
            if self._sentido and agora - self._virou_em < MEIO_VAIVEM_DO_ACENDE_S:
                return self.brilho  # virar agora seria passar do teto: segura o brilho
            self._sentido, self._virou_em = sentido, agora
        passo = TETO_DO_ACENDE_POR_S * decorrido
        self.brilho = min(alvo, self.brilho + passo) if sentido > 0 else max(
            alvo, self.brilho - passo)
        return self.brilho


def descida_do_reage_s(ritmo: int) -> float:
    """O clarão do aperto desce de 2 s no ritmo 1 a 0,5 s no ritmo 10."""
    return _entre_ritmos(ritmo, 2.0, 0.5)


def tempo_da_inclinacao_s(ritmo: int) -> float:
    """A constante do alisamento da inclinação: de 0,6 s no ritmo 1 a 0,05 s no ritmo 10."""
    return _entre_ritmos(ritmo, 0.6, 0.05)


@dataclass(frozen=True)
class Entrada:
    """O que a mão faz num controle, lido do aparelho dele (nada daqui escreve nele).

    ``apertos`` é o contador de bordas de cada botão (``EvdevSnapshot.apertos``); ``gravidade``
    é o acelerômetro em g; ``dedo`` é ``(x, y)`` de 0 a 1 no touchpad, ``None`` sem dedo. Cada
    campo é ``None`` quando o dado não veio: o efeito segura o que tinha. ``som`` é
    ``(nivel, agudos)`` de 0 a 1 do monitor da saída padrão: a energia relativa e a fração dela
    que é aguda. ``carga`` é ``(porcentagem, estado)`` DESTE controle; ``calor`` é a fração de
    0 a 1 do caminho entre o frio e o limite do sensor mais quente da máquina.
    """

    apertos: Mapping[str, int] | None = None
    gravidade: tuple[float, float, float] | None = None
    dedo: tuple[float, float] | None = None
    som: tuple[float, float] | None = None
    carga: tuple[int | None, str | None] | None = None
    calor: float | None = None


def _misturar(de: RGB, para: RGB, u: float) -> RGB:
    """A cor entre ``de`` (u=0) e ``para`` (u=1), em linha reta."""
    u = max(0.0, min(1.0, u))
    return (_inteiro(de[0] + (para[0] - de[0]) * u), _inteiro(de[1] + (para[1] - de[1]) * u),
            _inteiro(de[2] + (para[2] - de[2]) * u))


def _andar_o_matiz(atual: float, alvo: float, passo: float) -> float:
    """O matiz de ``atual`` rumo a ``alvo`` pelo caminho curto da roda, em no máximo ``passo``."""
    falta = (alvo - atual + 0.5) % 1.0 - 0.5
    if abs(falta) <= passo:
        return alvo % 1.0
    return (atual + math.copysign(passo, falta)) % 1.0


def _matiz_na_cor(matiz: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(matiz % 1.0, 1.0, 1.0)
    return (_inteiro(r * 255), _inteiro(g * 255), _inteiro(b * 255))


class ReageAoBotao:
    """O «Reage ao botão» de UM controle: o aperto acende a barra, e ela apaga devagar.

    O símbolo apertado dá a cor (△ verde, ○ vermelho, ✕ azul, □ rosa) e qualquer outro botão
    acende na cor escolhida do efeito. O primeiro tique só aprende os contadores (o que já foi
    apertado antes não acende). O brilho sobe em meio cosseno e desce no ritmo; sem aperto a
    barra fica na cor escolhida no piso, nunca apaga. Nunca mais de três subidas em 1 s:
    aperto a mais, dentro da janela, é lido e NÃO acende (a regra dos três clarões por segundo,
    D-2210-A-LUZ-GANHA-ONDA-E-RELAMPAGO).
    """

    def __init__(self, base: RGB, ritmo: int) -> None:
        self._base = base
        self._descida = descida_do_reage_s(ritmo)
        self._vistos: dict[str, int] | None = None
        self._subidas: deque[float] = deque()
        self._inicio: float | None = None
        self._de: tuple[RGB, float] = (base, PISO_DO_REAGE)
        self._para: RGB = base

    def _estado(self, agora: float) -> tuple[RGB, float]:
        """A cor e o brilho (0 a 1) de ``agora``."""
        if self._inicio is None:
            return self._base, PISO_DO_REAGE
        dt = agora - self._inicio
        cor_de, brilho_de = self._de
        if dt < SUBIDA_DO_REAGE_S:
            u = _suave(dt / SUBIDA_DO_REAGE_S)
            return _misturar(cor_de, self._para, u), brilho_de + (1.0 - brilho_de) * u
        u = (dt - SUBIDA_DO_REAGE_S) / self._descida
        if u >= 1.0:
            return self._base, PISO_DO_REAGE
        solta = _suave(u)
        return _misturar(self._para, self._base, solta), PISO_DO_REAGE + (
            1.0 - PISO_DO_REAGE) * (1.0 - solta)

    def _apertar(self, nomes: list[str], agora: float) -> bool:
        """Acende pelo aperto, se a janela de três subidas deixar; devolve se acendeu."""
        while self._subidas and agora - self._subidas[0] >= 1.0:
            self._subidas.popleft()
        if len(self._subidas) >= SUBIDAS_DO_REAGE_POR_S:
            return False
        simbolo = next((n for n in nomes if n in CORES_DOS_SIMBOLOS), None)
        self._de = self._estado(agora)
        self._para = CORES_DOS_SIMBOLOS[simbolo] if simbolo else self._base
        self._inicio = agora
        self._subidas.append(agora)
        return True

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        """A cor da barra em ``agora``, com os apertos que a ``entrada`` trouxe."""
        contagens = entrada.apertos
        if contagens is not None:
            if self._vistos is not None:
                novos = sorted(n for n, c in contagens.items() if c > self._vistos.get(n, 0))
                if novos:
                    self._apertar(novos, agora)
            self._vistos = dict(contagens)
        cor, brilho = self._estado(agora)
        return _escalar(cor, brilho)


#: De onde o anel da Ondulação parte: os botões da esquerda da luzinha 0, os da direita da 4, e
#: qualquer outro (o PS) da do meio, abrindo para os dois lados.
BOTOES_DA_ESQUERDA = frozenset(
    {"dpad_up", "dpad_down", "dpad_left", "dpad_right", "l1", "l2_btn", "l3", "create"})
BOTOES_DA_DIREITA = frozenset(
    {"triangle", "circle", "cross", "square", "r1", "r2_btn", "r3", "options"})


def passo_da_ondulacao_s(ritmo: int) -> float:
    """Quanto o anel leva de uma luzinha à seguinte: de 0,15 s no ritmo 1 a 0,06 s no 10."""
    return _entre_ritmos(ritmo, 0.15, 0.06)


def origem_do_anel(nome: str) -> int:
    """A luzinha de onde o anel parte para o botão ``nome``."""
    if nome in BOTOES_DA_ESQUERDA:
        return 0
    if nome in BOTOES_DA_DIREITA:
        return LEDS_DA_ONDA - 1
    return LED_DO_MEIO_DA_ONDA


class Ondulacao(ReageAoBotao):
    """A «Ondulação» de UM controle: a barra do Reage ao botão e um anel que corre pelas luzinhas.

    O anel parte do lado do botão e se abre, uma luzinha por passo, e as já acesas ficam; com as
    cinco acesas por um passo, o número do jogador volta (``None``). A luzinha que o anel apaga ao
    partir volta acesa quando ele a alcança, então cada luzinha sobe no máximo uma vez por aperto
    aceito. O aperto que a janela de três subidas recusa não ondula.
    """

    def __init__(self, base: RGB, ritmo: int) -> None:
        super().__init__(base, ritmo)
        self._passo = passo_da_ondulacao_s(ritmo)
        self._anel: tuple[int, float] | None = None

    def _apertar(self, nomes: list[str], agora: float) -> bool:
        if not super()._apertar(nomes, agora):
            return False
        nome = next((n for n in nomes if n in CORES_DOS_SIMBOLOS), nomes[0])
        self._anel = (origem_do_anel(nome), agora)
        return True

    def _luzinhas(self, agora: float) -> tuple[bool, bool, bool, bool, bool] | None:
        if self._anel is None:
            return None
        origem, inicio = self._anel
        passos = int(max(0.0, agora - inicio) / self._passo)
        if passos > max(origem, LEDS_DA_ONDA - 1 - origem):
            self._anel = None
            return None
        a, b, c, d, e = (abs(led - origem) <= passos for led in range(LEDS_DA_ONDA))
        return (a, b, c, d, e)

    def quadro(self, entrada: Entrada, agora: float) -> Quadro:
        cor = self.andar(entrada, agora)
        return Quadro(cor, self._luzinhas(agora))


class Inclinacao:
    """A «Inclinação» de UM controle: a cor gira pela roda conforme o controle inclina.

    O ângulo é o da gravidade no plano x-z do acelerômetro (o lado que aponta para baixo), como
    fração de volta; passar de uma volta não salta, porque o matiz é circular. A leitura é
    alisada (``tempo_da_inclinacao_s``) e a roda não gira mais depressa que
    ``VOLTAS_DO_MATIZ_POR_S``. Deitado (menos que ``INCLINACAO_MINIMA_G`` no plano), nenhum lado
    aponta para baixo e a cor fica. Sem leitura, fica a última cor (a branca, se nunca houve).
    """

    def __init__(self, ritmo: int) -> None:
        self._tau = tempo_da_inclinacao_s(ritmo)
        self._vetor: tuple[float, float] | None = None
        self._matiz: float | None = None
        self._visto_em: float | None = None

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        g = entrada.gravidade
        if g is not None and math.sqrt(sum(c * c for c in g)) >= GRAVIDADE_MINIMA_G:
            if self._vetor is None:
                self._vetor = (g[0], g[2])
            else:
                fator = 1.0 - math.exp(-decorrido / self._tau)
                self._vetor = (
                    self._vetor[0] + fator * (g[0] - self._vetor[0]),
                    self._vetor[1] + fator * (g[2] - self._vetor[1]),
                )
            if math.hypot(*self._vetor) >= INCLINACAO_MINIMA_G:
                alvo = (math.atan2(self._vetor[0], self._vetor[1]) / (2.0 * math.pi)) % 1.0
                self._matiz = alvo if self._matiz is None else _andar_o_matiz(
                    self._matiz, alvo, VOLTAS_DO_MATIZ_POR_S * decorrido)
        if self._matiz is None:
            return (255, 255, 255)
        return _matiz_na_cor(self._matiz)


class DedoNoTouchpad:
    """O «Dedo no touchpad» de UM controle: a posição do dedo dá a cor.

    Horizontal é o matiz (``VOLTA_DO_TOQUE``), vertical é o brilho (em cima é o cheio, embaixo é
    o piso). Sem dedo fica a última cor (a branca, se nunca houve). O matiz e o brilho andam
    com os mesmos freios dos outros efeitos: a roda não passa de ``VOLTAS_DO_MATIZ_POR_S`` e o
    brilho tem o teto de três vaivéns por segundo do ``BrilhoDoAcende``.
    """

    def __init__(self) -> None:
        self._matiz: float | None = None
        self._curso = 1.0
        self._brilho = BrilhoDoAcende(1.0)
        self._visto_em: float | None = None

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        dedo = entrada.dedo
        if dedo is not None:
            alvo = max(0.0, min(1.0, dedo[0])) * VOLTA_DO_TOQUE
            self._matiz = alvo if self._matiz is None else _andar_o_matiz(
                self._matiz, alvo, VOLTAS_DO_MATIZ_POR_S * decorrido)
            self._curso = 1.0 - max(0.0, min(1.0, dedo[1]))
        brilho = self._brilho.andar(self._curso, agora)
        if self._matiz is None:
            return _escalar((255, 255, 255), brilho)
        return _escalar(_matiz_na_cor(self._matiz), brilho)


#: O «Ao som» sobe depressa e desce devagar (cauda de 1 s no ritmo 1, 0,2 s no 10).
SUBIDA_DO_SOM_S = 0.03
#: Os agudos mudam a cor devagar: a barra não pisca de cor a cada pancada de prato.
TEMPO_DOS_AGUDOS_S = 0.3
#: O máximo de branco que os agudos misturam na cor escolhida (a barra nunca vira só branca).
BRANCO_DOS_AGUDOS = 0.8


def descida_do_som_s(ritmo: int) -> float:
    """A cauda do «Ao som»: de 1 s no ritmo 1 a 0,2 s no ritmo 10."""
    return _entre_ritmos(ritmo, 1.0, 0.2)


class AoSom:
    """O «Ao som» de UM controle: o brilho segue a energia do som da saída padrão.

    ``Entrada.som`` traz ``(nivel, agudos)``: o nível de 0 a 1 é a energia do som contra o pico
    recente dele (o volume da máquina não muda o desenho), e ``agudos`` é a fração dela acima da
    faixa dos graves. O nível sobe em ``SUBIDA_DO_SOM_S`` e desce na cauda do ritmo; os graves
    deixam a cor escolhida, os agudos a puxam para o branco (até ``BRANCO_DOS_AGUDOS``). O brilho
    sai pelo ``BrilhoDoAcende``: piso de 0,25 (nunca preto, mesmo no silêncio) e no máximo três
    vaivéns por segundo (D-2210-A-LUZ-GANHA-ONDA-E-RELAMPAGO). Sem leitura, o nível cai a zero.
    """

    def __init__(self, base: RGB, ritmo: int) -> None:
        self._base = base
        self._cauda = descida_do_som_s(ritmo)
        self._nivel = 0.0
        self._agudos = 0.0
        self._brilho = BrilhoDoAcende(0.0)
        self._visto_em: float | None = None

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        lido = entrada.som
        nivel, agudos = (0.0, self._agudos) if lido is None else (
            max(0.0, min(1.0, lido[0])), max(0.0, min(1.0, lido[1])))
        tempo = SUBIDA_DO_SOM_S if nivel > self._nivel else self._cauda
        self._nivel += (nivel - self._nivel) * (1.0 - math.exp(-decorrido / tempo))
        if lido is not None:
            self._agudos += (agudos - self._agudos) * (
                1.0 - math.exp(-decorrido / TEMPO_DOS_AGUDOS_S))
        cor = _misturar(self._base, (255, 255, 255), self._agudos * BRANCO_DOS_AGUDOS)
        return _escalar(cor, self._brilho.andar(self._nivel, agora))


#: A Aurora: um ciclo inteiro pelas cores dura de 60 s (ritmo 1) a 20 s (ritmo 10).
#: Com uma cor só, ela vai até os vizinhos dessa cor na roda (40 graus para cada lado).
VIZINHANCA_DA_AURORA = 40.0 / 360.0
TETO_DE_CORES_DA_AURORA = 3


def periodo_da_aurora_s(ritmo: int) -> float:
    """Um ciclo inteiro da Aurora: de 60 s no ritmo 1 a 20 s no ritmo 10."""
    return _entre_ritmos(ritmo, 60.0, 20.0)


def _nunca_preta(cor: RGB) -> RGB:
    """O preto puro vira o piso de brilho da casa: a luz do controle nunca sai preta."""
    return cor if max(cor) > 0 else _escalar((255, 255, 255), PISO_DO_ACENDE)


def cores_da_aurora(cores: Sequence[RGB]) -> tuple[RGB, ...]:
    """As cores por onde a Aurora passa: as escolhidas (até três) ou a escolhida e os vizinhos."""
    if len(cores) >= 2:
        return tuple(cores[:TETO_DE_CORES_DA_AURORA])
    base = cores[0] if cores else (255, 255, 255)
    return (base, _com_o_matiz_andado(base, VIZINHANCA_DA_AURORA),
            _com_o_matiz_andado(base, -VIZINHANCA_DA_AURORA))


#: Cada controle da mesa anda esta fração de ciclo atrás do anterior, como o arco-íris.
DEFASAGEM_DA_AURORA = 1.0 / 8.0


def cor_da_aurora(efeito: EfeitoDaLuz, t: float, lugar: int = 0) -> RGB:
    """A cor da Aurora em ``t``: de uma cor à seguinte, em meio cosseno, e de volta à primeira.

    ``lugar`` (0 a 3) é o posto do controle na mesa: cada um anda 1/8 de ciclo atrás do anterior.
    """
    cores = cores_da_aurora(efeito.cores)
    fase = t / periodo_da_aurora_s(efeito.ritmo) - lugar * DEFASAGEM_DA_AURORA
    posicao = fase % 1.0 * len(cores)
    indice = int(posicao)
    cor = _misturar(cores[indice % len(cores)], cores[(indice + 1) % len(cores)],
                    _suave(posicao - indice))
    return _nunca_preta(cor)


#: A «Cor da bateria»: vermelha até 10%, amarela em 50%, verde em 100%, e entre os pontos a cor
#: anda em linha reta pelo matiz.
CARGA_DO_VERMELHO_PCT = 10
CARGA_DO_AMARELO_PCT = 50
MATIZ_DO_AMARELO = 60.0 / 360.0
MATIZ_DO_VERDE = 120.0 / 360.0


def matiz_da_carga(pct: float) -> float:
    """O matiz da carga de 0 a 100: vermelho até 10, amarelo em 50, verde em 100."""
    if pct <= CARGA_DO_VERMELHO_PCT:
        return 0.0
    if pct <= CARGA_DO_AMARELO_PCT:
        return MATIZ_DO_AMARELO * (pct - CARGA_DO_VERMELHO_PCT) / (
            CARGA_DO_AMARELO_PCT - CARGA_DO_VERMELHO_PCT)
    return MATIZ_DO_AMARELO + (MATIZ_DO_VERDE - MATIZ_DO_AMARELO) * (
        min(100.0, pct) - CARGA_DO_AMARELO_PCT) / (100.0 - CARGA_DO_AMARELO_PCT)


def cor_da_carga(pct: float) -> RGB:
    """A cor da carga ``pct`` (0 a 100), saturada."""
    return _matiz_na_cor(matiz_da_carga(pct))


#: Sem leitura (sem controle lido, sem sensor): o branco no piso, que não é nenhuma cor de dado.
COR_SEM_LEITURA: RGB = _escalar((255, 255, 255), PISO_DO_ACENDE)


class CorDaBateria:
    """A «Cor da bateria» de UM controle: a cor segue a carga DELE.

    Verde cheia, amarelo na metade, vermelho no fim (``matiz_da_carga``). Carregando, a luz respira
    devagar (``RITMO_DA_BATERIA``), do piso à cor cheia, sem nunca apagar. Sem carga lida ainda
    fica ``COR_SEM_LEITURA``; uma leitura que falha depois segura a última.
    """

    def __init__(self, ritmo: int = RITMO_DA_BATERIA) -> None:
        self._periodo = periodo_do_respirar_s(ritmo)
        self._pct: int | None = None
        self._estado: str | None = None

    @property
    def sem_leitura(self) -> bool:
        return self._pct is None

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        carga = entrada.carga
        if carga is not None and isinstance(carga[0], int) and 0 < carga[0] <= 100:
            self._pct, self._estado = carga
        if self._pct is None:
            return COR_SEM_LEITURA
        cor = cor_da_carga(self._pct)
        if self._estado != "carregando":
            return cor
        fase = 0.5 - 0.5 * math.cos(2.0 * math.pi * agora / self._periodo)
        return _escalar(cor, PISO_DO_ACENDE + (1.0 - PISO_DO_ACENDE) * fase)


#: A «Cor da temperatura»: o calor anda para a leitura nova nisto, e a luz nunca salta.
TEMPO_DO_CALOR_S = 2.0
#: O matiz do azul frio; o quente é o vermelho, em 0.
MATIZ_DO_FRIO = 240.0 / 360.0


def cor_do_calor(calor: float) -> RGB:
    """O azul do frio (0) ao vermelho do limite do sensor (1), pelo matiz."""
    return _matiz_na_cor((1.0 - max(0.0, min(1.0, calor))) * MATIZ_DO_FRIO)


class CorDaTemperatura:
    """A «Cor da temperatura» de UM controle: azul frio, vermelho quente.

    ``Entrada.calor`` já é a fração do caminho entre o frio e o limite do sensor mais quente, com
    o limite descoberto do ``hwmon`` (``integrations/temperatura_da_maquina``). O calor é alisado
    (``TEMPO_DO_CALOR_S``), então a cor nunca pisca. Sem sensor lido, ``sem_leitura`` é verdade e a
    barra fica em ``COR_SEM_LEITURA``: ela não inventa uma temperatura.
    """

    def __init__(self) -> None:
        self._calor: float | None = None
        self._visto_em: float | None = None

    @property
    def sem_leitura(self) -> bool:
        return self._calor is None

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        lido = entrada.calor
        if lido is not None:
            lido = max(0.0, min(1.0, lido))
            if self._calor is None:
                self._calor = lido
            else:
                self._calor += (lido - self._calor) * (
                    1.0 - math.exp(-decorrido / TEMPO_DO_CALOR_S))
        return COR_SEM_LEITURA if self._calor is None else cor_do_calor(self._calor)


@dataclass(frozen=True)
class Quadro:
    """O que um efeito com luzinhas manda ao controle: a barra e as luzinhas do mesmo quadro.

    ``luzinhas`` é o que acende nas cinco luzinhas do jogador; ``None`` é o número do jogador,
    como o perfil o tem (quem escreve o quadro sabe qual é).
    """

    cor: RGB
    luzinhas: tuple[bool, bool, bool, bool, bool] | None = None


#: As Estrelas: cada cintilada e cada volta do número duram isto (sorteado), esticado pelo
#: ritmo. Uma cintilada e o número que a segue somam ao menos 0,86 s, então uma luzinha acende no
#: máximo duas vezes por segundo, abaixo do teto de três (WCAG 2.3.1).
CINTILADA_S = (0.36, 0.8)
NUMERO_S = (0.5, 1.4)
#: Quantas luzinhas uma cintilada acende, no mínimo e no máximo (nunca as cinco: isso é o número).
ESTRELAS_POR_CINTILADA = (1, 3)
#: A barra das Estrelas fica baixa e acompanha as luzinhas por cima disto, alisada.
NIVEL_DA_BARRA_DAS_ESTRELAS = 0.3
SOBE_A_BARRA_POR_ESTRELA = 0.1
TEMPO_DA_BARRA_DAS_ESTRELAS_S = 0.4
DEGRAUS_DA_BARRA_DAS_ESTRELAS = 16


def esticar_das_estrelas(ritmo: int) -> float:
    """O quanto as Estrelas esticam os tempos: 2,5 vezes no ritmo 1, 1 no ritmo 10."""
    return _entre_ritmos(ritmo, 2.5, 1.0)


class Estrelas:
    """As «Estrelas» de UM controle: as luzinhas cintilam ao acaso e a barra acompanha baixinho.

    O acaso nasce da semente do controle (cada um cintila diferente, e o teste é repetível). A
    luzinha cintila em ``CINTILADA_S`` e entre uma cintilada e outra o número do jogador volta
    (``Quadro.luzinhas`` ``None``). A barra fica entre 0,3 e 0,6 da cor escolhida, alisada e em
    degraus, para não gastar um report a cada tique: nunca preta e nunca pisca.
    """

    def __init__(self, base: RGB, ritmo: int, semente: int = 0) -> None:
        self._base = base
        self._rng = random.Random(semente)
        self._estica = esticar_das_estrelas(ritmo)
        self._acesas: tuple[bool, bool, bool, bool, bool] | None = None
        self._ate: float | None = None
        self._nivel = NIVEL_DA_BARRA_DAS_ESTRELAS
        self._visto_em: float | None = None

    def _proxima_fase(self, agora: float) -> None:
        """Passa da cintilada ao número e do número à cintilada, num tempo sorteado."""
        if self._acesas is None:  # estava no número (ou no começo): cintila
            a = set(self._rng.sample(range(5), self._rng.randint(*ESTRELAS_POR_CINTILADA)))
            self._acesas = (0 in a, 1 in a, 2 in a, 3 in a, 4 in a)
            tempo = self._rng.uniform(*CINTILADA_S)
        else:
            self._acesas = None
            tempo = self._rng.uniform(*NUMERO_S)
        self._ate = agora + tempo * self._estica

    def quadro(self, entrada: Entrada, agora: float) -> Quadro:
        decorrido = 0.0 if self._visto_em is None else max(0.0, agora - self._visto_em)
        self._visto_em = agora
        if self._ate is None or agora >= self._ate:
            self._proxima_fase(agora)
        acesas = 0 if self._acesas is None else sum(self._acesas)
        alvo = NIVEL_DA_BARRA_DAS_ESTRELAS + SOBE_A_BARRA_POR_ESTRELA * acesas
        self._nivel += (alvo - self._nivel) * (
            1.0 - math.exp(-decorrido / TEMPO_DA_BARRA_DAS_ESTRELAS_S))
        em_degraus = (
            round(self._nivel * DEGRAUS_DA_BARRA_DAS_ESTRELAS) / DEGRAUS_DA_BARRA_DAS_ESTRELAS)
        return Quadro(_escalar(self._base, max(NIVEL_DA_BARRA_DAS_ESTRELAS, em_degraus)),
                      self._acesas)

    def andar(self, entrada: Entrada, agora: float) -> RGB:
        return self.quadro(entrada, agora).cor


EstadoDaMao = (ReageAoBotao | Ondulacao | Inclinacao | DedoNoTouchpad | AoSom | CorDaBateria
               | CorDaTemperatura | Estrelas)


def estado_da_mao(efeito: EfeitoDaLuz, semente: int = 0) -> EstadoDaMao | None:
    """O estado novo de UM controle para o efeito, ou ``None`` se o efeito não tem estado.

    ``semente`` é a do controle: só as Estrelas a usam, para cintilar diferente em cada um.
    """
    if efeito.base == "reage-ao-botao":
        return ReageAoBotao((efeito.cores or ((255, 255, 255),))[0], efeito.ritmo)
    if efeito.base == "ondulacao":
        return Ondulacao((efeito.cores or ((255, 255, 255),))[0], efeito.ritmo)
    if efeito.base == "inclinacao":
        return Inclinacao(efeito.ritmo)
    if efeito.base == "dedo-no-touchpad":
        return DedoNoTouchpad()
    if efeito.base == "ao-som":
        return AoSom((efeito.cores or ((255, 255, 255),))[0], efeito.ritmo)
    if efeito.base == "estrelas":
        return Estrelas((efeito.cores or ((255, 255, 255),))[0], efeito.ritmo, semente)
    if efeito.base == "cor-da-bateria":
        return CorDaBateria()
    if efeito.base == "cor-da-temperatura":
        return CorDaTemperatura()
    return None


def bateria_acabando(pct: object, estado: object) -> bool:
    """A carga está abaixo do limiar e o controle não está no cabo?"""
    return (isinstance(pct, int) and 0 < pct < LIMIAR_DE_BATERIA_PCT
            and estado not in ESTADOS_DE_CARGA_EM_DIA)


def matiz_do_arco_iris(t: float, ritmo: int, posicao: int = 0) -> float:
    """O matiz do arco-íris em ``t``, com um quarto de volta de defasagem por controle."""
    return (t / periodo_do_arco_iris_s(ritmo) + DEFASAGEM_DO_ARCO_IRIS * posicao) % 1.0


#: O Respira em cores: cada respiração anda 0,618 de volta na roda (137 graus da anterior), e cada
#: lugar da mesa um quarto de volta, no relógio comum: os quatro nunca na mesma cor.
PASSO_DO_RESPIRA_EM_CORES = 0.618
DEFASAGEM_DO_RESPIRA_EM_CORES = 0.25


def matiz_do_respira_em_cores(t: float, ritmo: int, posicao: int = 0) -> float:
    """O matiz da respiração em curso: só troca no fundo, quando uma respiração dá a vez à outra."""
    respiracao = math.floor(t / periodo_do_respirar_s(ritmo))
    return (PASSO_DO_RESPIRA_EM_CORES * respiracao + DEFASAGEM_DO_RESPIRA_EM_CORES * posicao) % 1.0


def cor_no_instante(
    efeito: EfeitoDaLuz,
    t: float,
    posicao: int = 0,
    semente: int = 0,
    amplitude: float = 1.0,
) -> RGB:
    """A cor do efeito no instante ``t`` (segundos), na intensidade cheia do perfil.

    ``posicao`` é o lugar do controle na mesa (0 a 3): o arco-íris e o Respira em cores a usam,
    para defasar um quarto de volta por controle. ``semente`` é do controle: só a chama a usa. O
    respirar, o piscar, a batida, a onda, o vaivém, o enche e o relâmpago usam uma cor por ciclo,
    em ordem; a chama e a maré, a primeira cor; o arco-íris e o Respira em cores ignoram as cores.
    ``amplitude`` (0 a 1) encurta os 30 graus da Maré (ver :func:`amplitude_da_mare`). Na onda e no
    vaivém a barra é o LED do meio; as cinco luzinhas do jogador saem de
    :func:`luzinhas_no_instante`, no mesmo quadro.
    """
    if efeito.base == "arco-iris":  # (noqa-acento) chave ASCII
        r, g, b = colorsys.hsv_to_rgb(matiz_do_arco_iris(t, efeito.ritmo, posicao), 1.0, 1.0)
        return (_inteiro(r * 255), _inteiro(g * 255), _inteiro(b * 255))
    if efeito.base == "aurora":
        return cor_da_aurora(efeito, t, posicao)
    if efeito.base == "respira-em-cores":
        cor = _matiz_na_cor(matiz_do_respira_em_cores(t, efeito.ritmo, posicao))
        return _escalar(cor, brilho_do_respirar(t, periodo_do_respirar_s(efeito.ritmo)))
    cores = efeito.cores or ((255, 255, 255),)
    if efeito.base in BASES_DE_DADO_VIVO:  # sem o dado vivo: a cor escolhida, parada
        return cores[0]
    if efeito.base == "fixa":  # a cor parada: o Acende varia o brilho, não a cor
        return cores[0]
    if efeito.base == "chama":
        brilho = brilho_da_chama(t, troca_da_chama_s(efeito.ritmo), semente)
        return _escalar(cores[0], brilho)
    if efeito.base == "mare":
        return _com_o_matiz_andado(
            cores[0], amplitude * deslocamento_da_mare(t, periodo_da_mare_s(efeito.ritmo))
        )
    if efeito.base == "batimento":  # (noqa-acento) chave ASCII
        periodo = periodo_da_batida_s(efeito.ritmo)
        cor = cores[int(t / periodo) % len(cores)]
        return _escalar(cor, brilho_da_batida(t, periodo))
    if efeito.base == "onda":
        periodo = periodo_da_onda_s(efeito.ritmo)
        cor = cores[int(t / periodo) % len(cores)]
        return _escalar(cor, brilho_da_onda(t, periodo))
    if efeito.base == "vaivem":
        periodo = periodo_do_vaivem_s(efeito.ritmo)
        cor = cores[int(t / periodo) % len(cores)]
        return _escalar(cor, brilho_do_vaivem(t, periodo))
    if efeito.base == "enche":
        passo = passo_do_enche_s(efeito.ritmo)
        cor = cores[int(t / (passo * PASSOS_DO_ENCHE)) % len(cores)]
        return _escalar(cor, brilho_do_enche(t, passo))
    if efeito.base == "relampago":
        periodo = periodo_do_relampago_s(efeito.ritmo)
        cor = cores[int(t / periodo) % len(cores)]
        return _escalar(cor, brilho_do_relampago(t, periodo))
    if efeito.base == "piscar":
        hz = frequencia_do_piscar_hz(efeito.ritmo)
        periodo = 1.0 / hz
        borda = min(BORDA_DO_PISCAR_S, periodo / 2)
        # A cor troca no meio do baixo, onde a luz está no piso, e nunca no alto.
        meio_do_baixo = 0.75 * periodo - borda / 2
        cor = cores[max(0, math.floor((t + periodo - meio_do_baixo) / periodo)) % len(cores)]
        return _escalar(cor, brilho_do_piscar(t, hz))
    periodo = periodo_do_respirar_s(efeito.ritmo)
    cor = cores[int(t / periodo) % len(cores)]
    return _escalar(cor, brilho_do_respirar(t, periodo))


__all__ = [
    "BASES_COM_LUZINHAS",
    "BASES_DE_DADO_VIVO",
    "BASES_DO_RELOGIO_COMUM",
    "BORDA_DO_PISCAR_S",
    "BOTOES_DA_DIREITA",
    "BOTOES_DA_ESQUERDA",
    "CORES_DOS_SIMBOLOS",
    "COR_SEM_LEITURA",
    "DEFASAGEM_DA_AURORA",
    "DEFASAGEM_DO_ARCO_IRIS",
    "DEFASAGEM_DO_RESPIRA_EM_CORES",
    "ESTADOS_DE_CARGA_EM_DIA",
    "LEDS_DA_ONDA",
    "LED_DO_MEIO_DA_ONDA",
    "LIMIAR_DA_LUZINHA_DA_ONDA",
    "LIMIAR_DE_BATERIA_PCT",
    "MEIO_VAIVEM_DO_ACENDE_S",
    "PASSOS_DO_ENCHE",
    "PASSO_DO_RESPIRA_EM_CORES",
    "PISO_DA_BATIDA",
    "PISO_DA_ONDA",
    "PISO_DO_ACENDE",
    "PISO_DO_PISCAR",
    "PISO_DO_RELAMPAGO",
    "PISO_DO_RESPIRAR",
    "RITMO_DA_BATERIA",
    "TETO_DO_ACENDE_POR_S",
    "TETO_DO_PISCAR_HZ",
    "VAIVENS_DO_ACENDE_POR_S",
    "AoSom",
    "BrilhoDoAcende",
    "CorDaBateria",
    "CorDaTemperatura",
    "DedoNoTouchpad",
    "Entrada",
    "EstadoDaMao",
    "Estrelas",
    "Inclinacao",
    "Ondulacao",
    "Quadro",
    "ReageAoBotao",
    "amplitude_da_mare",
    "bateria_acabando",
    "brilho_da_batida",
    "brilho_da_chama",
    "brilho_da_onda",
    "brilho_do_acende",
    "brilho_do_enche",
    "brilho_do_piscar",
    "brilho_do_relampago",
    "brilho_do_respirar",
    "brilho_do_vaivem",
    "brilhos_da_onda",
    "brilhos_do_vaivem",
    "cor_da_aurora",
    "cor_da_carga",
    "cor_do_calor",
    "cor_no_instante",
    "cores_da_aurora",
    "crista_do_vaivem",
    "descida_do_reage_s",
    "descida_do_som_s",
    "deslocamento_da_mare",
    "estado_da_mao",
    "frequencia_do_piscar_hz",
    "luzinhas_da_onda",
    "luzinhas_do_enche",
    "luzinhas_no_instante",
    "matiz_da_carga",
    "matiz_do_arco_iris",
    "matiz_do_respira_em_cores",
    "origem_do_anel",
    "passo_da_ondulacao_s",
    "passo_do_enche_s",
    "periodo_da_aurora_s",
    "periodo_da_batida_s",
    "periodo_da_mare_s",
    "periodo_da_onda_s",
    "periodo_do_arco_iris_s",
    "periodo_do_relampago_s",
    "periodo_do_respirar_s",
    "periodo_do_vaivem_s",
    "tempo_da_inclinacao_s",
    "troca_da_chama_s",
]
