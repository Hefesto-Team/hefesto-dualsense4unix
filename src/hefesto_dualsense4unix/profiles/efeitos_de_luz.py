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
from collections.abc import Sequence

from hefesto_dualsense4unix.profiles.estilos_de_jogo import DISTANCIA_MINIMA
from hefesto_dualsense4unix.profiles.schema import EfeitoDaLuz

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
BASES_DO_RELOGIO_COMUM = frozenset({"arco-iris", "mare"})  # (noqa-acento) chave ASCII

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


def bateria_acabando(pct: object, estado: object) -> bool:
    """A carga está abaixo do limiar e o controle não está no cabo?"""
    return (isinstance(pct, int) and 0 < pct < LIMIAR_DE_BATERIA_PCT
            and estado not in ESTADOS_DE_CARGA_EM_DIA)


def matiz_do_arco_iris(t: float, ritmo: int, posicao: int = 0) -> float:
    """O matiz do arco-íris em ``t``, com um quarto de volta de defasagem por controle."""
    return (t / periodo_do_arco_iris_s(ritmo) + DEFASAGEM_DO_ARCO_IRIS * posicao) % 1.0


def cor_no_instante(
    efeito: EfeitoDaLuz,
    t: float,
    posicao: int = 0,
    semente: int = 0,
    amplitude: float = 1.0,
) -> RGB:
    """A cor do efeito no instante ``t`` (segundos), na intensidade cheia do perfil.

    ``posicao`` é o lugar do controle na mesa (0 a 3): só o arco-íris a usa, para defasar um
    quarto de volta por controle. ``semente`` é do controle: só a chama a usa. O respirar, o
    piscar, a batida, a onda e o relâmpago usam uma cor por ciclo, em ordem; a chama e a maré, a
    primeira cor; o arco-íris ignora as cores. ``amplitude`` (0 a 1) encurta os 30 graus da
    Maré (ver :func:`amplitude_da_mare`). A onda, no daemon, é só da barra (o LED do meio);
    ``brilhos_da_onda`` desenha os cinco LEDs do jogador para quando o quadro único os levar.
    """
    if efeito.base == "arco-iris":  # (noqa-acento) chave ASCII
        r, g, b = colorsys.hsv_to_rgb(matiz_do_arco_iris(t, efeito.ritmo, posicao), 1.0, 1.0)
        return (_inteiro(r * 255), _inteiro(g * 255), _inteiro(b * 255))
    cores = efeito.cores or ((255, 255, 255),)
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
    "BASES_DO_RELOGIO_COMUM",
    "BORDA_DO_PISCAR_S",
    "DEFASAGEM_DO_ARCO_IRIS",
    "ESTADOS_DE_CARGA_EM_DIA",
    "LEDS_DA_ONDA",
    "LED_DO_MEIO_DA_ONDA",
    "LIMIAR_DE_BATERIA_PCT",
    "MEIO_VAIVEM_DO_ACENDE_S",
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
    "BrilhoDoAcende",
    "amplitude_da_mare",
    "bateria_acabando",
    "brilho_da_batida",
    "brilho_da_chama",
    "brilho_da_onda",
    "brilho_do_acende",
    "brilho_do_piscar",
    "brilho_do_relampago",
    "brilho_do_respirar",
    "brilhos_da_onda",
    "cor_no_instante",
    "deslocamento_da_mare",
    "frequencia_do_piscar_hz",
    "matiz_do_arco_iris",
    "periodo_da_batida_s",
    "periodo_da_mare_s",
    "periodo_da_onda_s",
    "periodo_do_arco_iris_s",
    "periodo_do_relampago_s",
    "periodo_do_respirar_s",
    "troca_da_chama_s",
]
