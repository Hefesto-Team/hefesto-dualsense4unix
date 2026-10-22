"""As formas do efeito háptico: do toque seco ao som no corpo (funções puras).

A háptica viaja como áudio de quatro canais a 48 kHz; o toque do tiro é uma forma de onda curta
somada aos canais dos atuadores: senos com um ataque e uma queda até zero. O disparo é da receita
do estilo; a forma é a escolha da pessoa, uma por controle (``efeito_haptico`` do perfil). O ganho
é o Sensor háptico, que age adiante: nada aqui lê barra nem perfil. O Som no corpo, o Grão e o
Motor de época são contínuos (o laço do tato os gera por tique). O Eco, o Grão e o Motor de época
o estilo pede e a lista da aba Vibração também mostra (20/10/2026): estão em ``ESCOLHAS``, que a
tela e o perfil validam.
"""
from __future__ import annotations

import functools
import math
import sys
from array import array
from dataclasses import dataclass

TAXA = 48_000

#: «Do estilo» é o automático (o que o estilo pede, e o Toque de hoje quando ele não pede nada);
#: «Sem efeito» cala o toque deste controle.
DO_ESTILO = "do_estilo"
SEM_EFEITO = "sem_efeito"
TOQUE = "toque"
IMPACTO = "impacto"
ESTALO = "estalo"
GUARDA = "guarda"
APARO = "aparo"
SOM_NO_CORPO = "som_no_corpo"
#: As três que o estilo pede e a lista mostra (20/10/2026), ao fim das escolhas.
ECO = "eco"
GRAO = "grao"  # (noqa-acento): chave
MOTOR_DE_EPOCA = "motor_de_epoca"

#: As escolhas, na ordem em que a tela as mostra. A chave é a que o perfil guarda.
ESCOLHAS: tuple[str, ...] = (
    DO_ESTILO, SEM_EFEITO, TOQUE, IMPACTO, ESTALO, GUARDA, APARO, SOM_NO_CORPO,
    ECO, GRAO, MOTOR_DE_EPOCA)

ROTULOS: dict[str, str] = {
    DO_ESTILO: "Do estilo",
    SEM_EFEITO: "Sem efeito",
    TOQUE: "Toque",
    IMPACTO: "Impacto",
    ESTALO: "Estalo",
    GUARDA: "Guarda",
    APARO: "Aparo",
    SOM_NO_CORPO: "Som no corpo",
    ECO: "Eco",
    GRAO: "Grão",
    MOTOR_DE_EPOCA: "Motor de época",
}

#: O que se sente, em uma linha (até 36 letras, para caber na coluna da lista).
DICAS: dict[str, str] = {
    DO_ESTILO: "O que o estilo pede",
    SEM_EFEITO: "O controle não toca",
    TOQUE: "Um toque seco e curto",
    IMPACTO: "Uma pancada funda",
    ESTALO: "Um clique fino",
    GUARDA: "Metal contra metal, médio",
    APARO: "Metal agudo, mais longo",
    SOM_NO_CORPO: "O grave do jogo vira tremor",
    ECO: "Um Impacto com cauda grave",
    GRAO: "Grãos finos e rápidos, sem parar",
    MOTOR_DE_EPOCA: "O zumbido grosso do rumble antigo",
}

#: As contínuas: o laço do tato as leva por tique, e nenhum toque de tiro as toca.
CONTINUAS = frozenset({SOM_NO_CORPO, GRAO, MOTOR_DE_EPOCA})

#: As formas longas: a Bateria longa as troca pelo Toque (as contínuas, por nada), e o rádio só as
#: toca com fatia livre.
FORMAS_LONGAS = frozenset({GUARDA, APARO, ECO} | CONTINUAS)

#: O que cada estilo pede da háptica (a tabela `S` da página de 19/10/2026): toda forma, inclusive
#: as contínuas (o Som no corpo da Corrida, o Grão da Simulação, o Motor de época do Retrô). O
#: estilo que não está aqui toca o Toque.
POR_ESTILO: dict[str, str] = {
    "fps": TOQUE,
    "acao": IMPACTO,  # (noqa-acento): chave
    "luta": IMPACTO,
    "souls": ECO,  # o Impacto com cauda grave de 300 ms: só o golpe forte reverbera
    "furtivo": ESTALO,
    "aventura": TOQUE,
    "terror": TOQUE,  # 80 ms: `duracao_da_vibracao_ms` do Terror
    "corrida": SOM_NO_CORPO,
    "simulacao": GRAO,  # grãos finos e rápidos: o chão, a pista ou a turbulência
    "esportes": IMPACTO,
    "plataforma": ESTALO,
    "ritmo": ESTALO,
    "retro": MOTOR_DE_EPOCA,  # soma o zumbido grosso quando o jogo vibra; sem rumble, mudo
    "maratona": TOQUE,
    "point_and_click": TOQUE,
    "visual_novel": TOQUE,
}


@dataclass(frozen=True)
class Forma:
    """Senos somados (``hz``, peso; os pesos somam 1), com ataque e duração em ms."""

    componentes: tuple[tuple[int, float], ...]
    ataque_ms: int
    #: ``None``: a duração vem do pedido (o Toque do estilo, de 25 a 60 ms).
    duracao_ms: int | None
    #: A cauda grave (o Eco): um seno de ``cauda_hz`` que nasce no fim do golpe e cai até zero em
    #: ``cauda_ms``, no ``cauda_peso`` da energia. Sem ``cauda_hz`` a forma não tem cauda.
    cauda_hz: int = 0
    cauda_ms: int = 0
    cauda_peso: float = 0.55


FORMAS: dict[str, Forma] = {
    TOQUE: Forma(((160, 1.0),), 3, None),
    IMPACTO: Forma(((60, 0.6), (160, 0.4)), 2, 80),
    ESTALO: Forma(((250, 1.0),), 1, 15),
    GUARDA: Forma(((115, 0.6), (220, 0.4)), 3, 850),
    APARO: Forma(((170, 0.5), (270, 0.5)), 3, 600),
    # o Impacto de 80 ms e uma cauda de 50 Hz de 300 ms, como o eco de um golpe pesado
    ECO: Forma(((60, 0.6), (160, 0.4)), 2, 380, 50, 300),
}

#: A Assinatura (20/10/2026): o Toque na nota de cada unidade, de 150 a 195 Hz de 15 em 15. A
#: nota é da cor do plástico (``daemon/subsystems/chegada``), e a forma é só do estilo: fora de
#: ``FORMAS`` e de ``ESCOLHAS``.
NOTAS_DA_ASSINATURA: tuple[int, ...] = (150, 165, 180, 195)
ASSINATURAS: dict[str, Forma] = {
    f"toque-{hz}": Forma(((hz, 1.0),), 3, None) for hz in NOTAS_DA_ASSINATURA
}


def forma_da_nota(hz: int | None) -> str:
    """A forma do Toque na nota ``hz``; o Toque de 160 Hz quando a unidade não tem nota."""
    chave = f"toque-{hz}"
    return chave if chave in ASSINATURAS else TOQUE


def amostras(
    chave: str, energia: float, duracao_ms: int | None = None, taxa: int = TAXA
) -> array[float]:
    """As amostras de UMA forma: sobe no ataque, cai até zero no fim, nunca passa de ``energia``."""
    if chave in (GRAO, MOTOR_DE_EPOCA):
        return _volta_da_continua(chave, energia, duracao_ms, taxa)
    forma = FORMAS.get(chave) or ASSINATURAS.get(chave)
    if forma is None:
        raise ValueError(
            f"forma de háptica desconhecida: {chave!r}. As que existem: "
            f"{', '.join((*FORMAS, GRAO, MOTOR_DE_EPOCA))}")
    duracao = forma.duracao_ms if forma.duracao_ms is not None else (duracao_ms or 40)
    n = max(2, round(taxa * max(1, int(duracao)) / 1000))
    forca = max(0.0, min(1.0, float(energia)))
    envelopes, ondas = _molde(chave, n, taxa)
    pares = zip(envelopes, ondas, strict=True)
    return array("f", [forca * envelope * onda for envelope, onda in pares])


@functools.lru_cache(maxsize=32)
def _molde(chave: str, n: int, taxa: int) -> tuple[array[float], array[float]]:
    """O envelope e a onda de uma forma, sem a força: a conta dos senos, feita uma vez por duração.

    O toque sai no laço do tato, no fio do daemon: a Guarda (850 ms, dois senos) custa uns 20 ms
    de conta, e refazê-la a cada tiro seguraria a entrada dos quatro controles.
    """
    forma = FORMAS.get(chave) or ASSINATURAS[chave]
    cauda = round(taxa * forma.cauda_ms / 1000) if forma.cauda_hz else 0
    corpo = max(2, n - cauda)
    ataque = max(1, min(corpo - 1, round(taxa * forma.ataque_ms / 1000)))
    passos = [(2.0 * math.pi * hz / taxa, peso) for hz, peso in forma.componentes]
    envelopes, ondas = array("d", bytes(8 * n)), array("d", bytes(8 * n))
    for i in range(min(n, corpo)):
        if i < ataque:
            envelopes[i] = i / ataque
        else:
            queda = corpo - 1 - ataque
            envelopes[i] = ((corpo - 1 - i) / queda) ** 2 if queda > 0 else 0.0
        ondas[i] = sum(peso * math.sin(passo * i) for passo, peso in passos)
    if cauda and n > corpo:
        # a cauda sobe em 20 ms e cai ao quadrado até zero; o fim do corpo já é zero, sem estalo
        sobe = max(1, min(cauda - 1, round(taxa * CAUDA_SOBE_MS / 1000)))
        passo_da_cauda = 2.0 * math.pi * forma.cauda_hz / taxa
        for j in range(n - corpo):
            i = corpo + j
            if j < sobe:
                envelopes[i] = forma.cauda_peso * j / sobe
            else:
                envelopes[i] = forma.cauda_peso * ((n - 1 - i) / (n - 1 - corpo - sobe)) ** 2
            ondas[i] = math.sin(passo_da_cauda * j)
    return envelopes, ondas


#: A cauda do Eco sobe em tantos ms (a pancada e o eco se separam).
CAUDA_SOBE_MS = 20


def escolha_valida(valor: object) -> str | None:
    """A escolha do perfil como chave conhecida; ``None`` quando não há escolha ou não se lê.

    ``None`` quer dizer «Do estilo»: o perfil que não escolheu nada se comporta como sempre.
    """
    return valor if isinstance(valor, str) and valor in ESCOLHAS and valor != DO_ESTILO else None


def forma_do_estilo(estilo: object) -> str:
    """A forma que o estilo pede; o Toque de hoje quando ele não pede nenhuma.

    A chave que saiu do catálogo (o Arco) vale pela do estilo que a recebeu.
    """
    if not isinstance(estilo, str):
        return TOQUE
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    return POR_ESTILO.get(str(chave_do_catalogo(estilo)), TOQUE)


def forma_que_vale(escolha: object, estilo: object, economia: bool = False) -> str | None:
    """A forma que toca de verdade, ou ``None`` quando este controle não toca.

    ``economia`` é a Bateria longa: Guarda, Aparo e Eco viram o Toque, e as contínuas calam.
    """
    chave = escolha_valida(escolha)
    if chave == SEM_EFEITO:
        return None
    if chave is None:
        chave = forma_do_estilo(estilo)
        if chave == SEM_EFEITO:  # o estilo que não toca nada (o Retrô)
            return None
    if economia and chave in FORMAS_LONGAS:
        return None if chave in CONTINUAS else TOQUE
    return chave


# --- O Som no corpo: o grave do som do jogo -------------------------------------------------

#: A faixa do corpo: abaixo de 40 Hz o atuador não responde, acima de 220 Hz já é toque.
CORTE_BAIXO_HZ = 40
CORTE_ALTO_HZ = 220
#: Valores de partida: o ganho é fixo (o Sensor háptico regula adiante) e o teto protege o atuador.
GANHO_DO_CORPO = 4.0
TETO_DO_CORPO = 0.7
_ESCALA_DO_PCM = 32768.0


class _Biquad:
    """Um filtro de segunda ordem (Butterworth), com o estado entre os pedaços."""

    def __init__(self, tipo: str, corte_hz: float, taxa: int) -> None:
        w = 2.0 * math.pi * corte_hz / taxa
        cos_w, alfa = math.cos(w), math.sin(w) / (2.0 * 0.7071067811865476)
        if tipo == "passa-baixa":
            b0 = b2 = (1.0 - cos_w) / 2.0
            b1 = 1.0 - cos_w
        else:
            b0 = b2 = (1.0 + cos_w) / 2.0
            b1 = -(1.0 + cos_w)
        a0 = 1.0 + alfa
        self.b0, self.b1, self.b2 = b0 / a0, b1 / a0, b2 / a0
        self.a1, self.a2 = (-2.0 * cos_w) / a0, (1.0 - alfa) / a0
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def passar(self, x: float) -> float:
        y = (self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2
             - self.a1 * self.y1 - self.a2 * self.y2)
        self.x2, self.x1 = self.x1, x
        self.y2, self.y1 = self.y1, y
        return y


class FiltroDoCorpo:
    """O som do jogo (PCM estéreo, s16le) vira o grave de 40 a 220 Hz, mono, com ganho e teto."""

    def __init__(self, taxa: int = TAXA) -> None:
        self.taxa = taxa
        self._alto = _Biquad("passa-alta", CORTE_BAIXO_HZ, taxa)
        self._baixo = _Biquad("passa-baixa", CORTE_ALTO_HZ, taxa)

    def processar(self, pcm: bytes) -> array[float]:
        """O pedaço filtrado. Meio quadro solto no fim do pedaço é descartado."""
        quadros = array("h")
        quadros.frombytes(pcm[: len(pcm) - len(pcm) % 4])
        if sys.byteorder != "little":  # pragma: no cover — o formato é little-endian
            quadros.byteswap()
        saida = array("f", bytes(4 * (len(quadros) // 2)))
        for i in range(len(saida)):
            mono = (quadros[2 * i] + quadros[2 * i + 1]) / (2.0 * _ESCALA_DO_PCM)
            y = GANHO_DO_CORPO * self._baixo.passar(self._alto.passar(mono))
            saida[i] = max(-TETO_DO_CORPO, min(TETO_DO_CORPO, y))
        return saida


# --- O Grão e o Motor de época: as contínuas que o estilo pede -----------------------------

#: O Grão: rajadas de 6 ms de um seno de 180 a 260 Hz, com 12 a 38 ms de silêncio entre uma e
#: outra (uns 32 grãos por segundo), na amplitude de 0,35 a 0,6 (abaixo do teto do corpo).
GRAO_MS = 6
GRAO_FOLGA_MIN_MS = 12
GRAO_FOLGA_VARIA_MS = 26
GRAO_HZ = (180, 200, 220, 240, 260)
GRAO_AMPLITUDES = (0.35, 0.48, 0.6)
_SEMENTE_DO_GRAO = 20_101_920

#: O Motor de época: um zumbido grosso de 30 a 50 Hz que SOBE devagar (arranque de 120 ms) e
#: ARRASTA ao parar (250 ms), no teto do corpo. A frequência segue a força do rumble do jogo.
EPOCA_HZ_MIN = 30.0
EPOCA_HZ_MAX = 50.0
EPOCA_ARRANQUE_S = 0.120
EPOCA_PARADA_S = 0.250
_EPOCA_HARMONICA = 0.18


@functools.lru_cache(maxsize=4)
def _graos_prontos(taxa: int) -> tuple[array[float], ...]:
    """Os grãos feitos: cada um é um seno com janela de Hann; a conta se faz uma vez por taxa."""
    n = max(4, round(taxa * GRAO_MS / 1000))
    prontos = []
    for hz in GRAO_HZ:
        for pico in GRAO_AMPLITUDES:
            passo = 2.0 * math.pi * hz / taxa
            prontos.append(array("f", [
                pico * (0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1))) * math.sin(passo * i)
                for i in range(n)]))
    return tuple(prontos)


class GeradorDoGrao:
    """Os grãos finos e rápidos, sem parar: sempre os mesmos para a mesma semente.

    O sorteio é um congruencial (sem ``random``): o que se ouve é função da semente e de quantas
    amostras já saíram, e nenhum grão passa do teto do corpo.
    """

    def __init__(self, taxa: int = TAXA, semente: int = _SEMENTE_DO_GRAO) -> None:
        self.taxa = taxa
        self._estado = (semente % 2_147_483_646) + 1
        self._graos = _graos_prontos(taxa)
        self._resto: array[float] = array("f")

    def _sortear(self) -> int:
        self._estado = (self._estado * 48_271) % 2_147_483_647
        return self._estado

    def gerar(self, n: int) -> array[float]:
        """As próximas ``n`` amostras (mono)."""
        while len(self._resto) < n:
            sorteio = self._sortear()
            self._resto.extend(self._graos[sorteio % len(self._graos)])
            folga_ms = GRAO_FOLGA_MIN_MS + (sorteio >> 8) % GRAO_FOLGA_VARIA_MS
            self._resto.extend(array("f", bytes(4 * round(self.taxa * folga_ms / 1000))))
        saida = self._resto[:n]
        self._resto = self._resto[n:]
        return saida


class GeradorDoMotorDeEpoca:
    """O zumbido do motor de peso: segue o nível do rumble do jogo, subindo e arrastando.

    ``gerar(n, nivel)`` dá ``n`` amostras com o alvo ``nivel`` (0 a 1, a força do rumble do jogo).
    A amplitude anda até o alvo num polo só, mais devagar na subida que no corpo do toque e mais
    devagar ainda na descida; a fase não reinicia entre um pedaço e outro. Com ``nivel`` zero e a
    amplitude já no fundo, o pedaço sai todo em silêncio.
    """

    def __init__(self, taxa: int = TAXA) -> None:
        self.taxa = taxa
        self._amplitude = 0.0
        self._fase = 0.0

    @property
    def amplitude(self) -> float:
        return self._amplitude

    @property
    def calado(self) -> bool:
        """A amplitude já arrastou até o silêncio."""
        return self._amplitude < 0.005

    def gerar(self, n: int, nivel: float) -> array[float]:
        if n <= 0:
            return array("f")
        alvo = max(0.0, min(1.0, float(nivel)))
        de = self._amplitude
        tau = EPOCA_ARRANQUE_S if alvo > de else EPOCA_PARADA_S
        ate = alvo + (de - alvo) * math.exp(-(n / self.taxa) / tau)
        if ate < 0.005 and alvo == 0.0:
            ate = 0.0
        hz = EPOCA_HZ_MIN + (EPOCA_HZ_MAX - EPOCA_HZ_MIN) * max(de, ate)
        passo = 2.0 * math.pi * hz / self.taxa
        fase, degrau = self._fase, (ate - de) / n
        saida = array("f", [
            TETO_DO_CORPO * (de + degrau * i)
            * ((1.0 - _EPOCA_HARMONICA) * math.sin(fase + passo * i)
               + _EPOCA_HARMONICA * math.sin(2.0 * (fase + passo * i)))
            for i in range(n)])
        self._fase = (fase + passo * n) % (2.0 * math.pi)
        self._amplitude = ate
        return saida


def _volta_da_continua(
    chave: str, energia: float, duracao_ms: int | None, taxa: int
) -> array[float]:
    """Um trecho finito de uma contínua, para o teste: sempre o mesmo, e em zero no fim.

    O Motor de época sobe com a ``energia`` como nível do rumble por 70 % do trecho e arrasta no
    resto; o Grão é a sequência dos grãos. O fim tem 3 ms de descida até zero.
    """
    n = max(2, round(taxa * max(1, int(duracao_ms or 200)) / 1000))
    forca = max(0.0, min(1.0, float(energia)))
    if chave == GRAO:
        brutas = GeradorDoGrao(taxa).gerar(n)
        saida = array("f", [forca * x for x in brutas])
    else:
        gerador = GeradorDoMotorDeEpoca(taxa)
        corte = max(1, round(n * 0.7))
        saida = gerador.gerar(corte, forca)
        saida.extend(gerador.gerar(n - corte, 0.0))
    descida = min(n, max(2, round(taxa * 0.003)))
    for i in range(descida):
        saida[n - 1 - i] *= i / descida
    return saida


# --- O timbre do rumble do jogo Xbox (O-RUMBLE-DO-JOGO-XBOX-GANHA-O-TIMBRE-DO-ESTILO-01) ---------

#: Os estilos que tocam o seno de hoje, byte a byte: sem pedido (Nativo, Personalizado), o que já
#: soma o timbre dele (o Retrô, com o Motor de época) e o Adulto, que não é estilo de golpe.
SEM_TIMBRE = frozenset({"nativo", "personalizado", "retro", "adulto"})
#: O contínuo que cada estilo NÃO veste (valores de partida, a validar na bancada): a Luta, a
#: Plataforma e o Ritmo vivem de golpe limpo; o Furtivo e os Esportes não pedem o corpo grave; o
#: Souls e os Esportes não pedem o Grão.
SEM_CORPO = frozenset({"luta", "plataforma", "ritmo", "furtivo", "esportes"})
SEM_GRAO = frozenset({"luta", "plataforma", "ritmo", "souls", "esportes"})  # (noqa-acento): chave
#: O corpo do contínuo grave: 40 Hz com a terceira harmônica (o peso dela), no canal do forte.
CORPO_HZ = 40
PESO_DA_HARMONICA = 0.33
#: O Grão do contínuo fino: grãos de 4 ms a 40 por segundo somados ao seno do fraco.
GRAOS_DO_TIMBRE_POR_S = 40  # (noqa-acento): constante
GRAO_DO_TIMBRE_MS = 4  # (noqa-acento): constante
GANHO_DO_GRAO_DO_TIMBRE = 0.6  # (noqa-acento): constante
#: A frequência de cada canal no seno de hoje: o forte (canal 3) e o fraco (canal 4).
HZ_DO_FORTE = 60
HZ_DO_FRACO = 160


def timbre_do_rumble(
    estilo: object, forma: str | None, classe: str | None, onda: str | None = None
) -> str | None:
    """A chave do timbre de uma classe do rumble neste controle; ``None`` é o seno de hoje.

    ``forma`` é a de :func:`forma_que_vale` do controle (a escolha dele ou a do estilo).
    """
    from hefesto_dualsense4unix.integrations import classe_do_rumble as classes
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    if not isinstance(estilo, str) or classe is None:
        return None
    chave = str(chave_do_catalogo(estilo))
    if chave in SEM_TIMBRE or forma is None:
        return None
    if classe == classes.PERIODICO:
        return f"periodico:{onda}" if onda not in (None, classes.SENO) else None
    if classe == classes.GOLPE:
        golpe = forma if forma in FORMAS or forma in ASSINATURAS else TOQUE
        return f"golpe:{golpe}"
    if classe == classes.CONTINUO_GRAVE:
        return None if chave in SEM_CORPO else "corpo"
    if classe == classes.CONTINUO_FINO:
        return None if chave in SEM_GRAO else "grao"  # (noqa-acento): chave
    return None


def _no_ciclo(hz: int, ciclo: int, taxa: int) -> int:
    """A frequência mais próxima que fecha o ciclo do tocador (20 Hz em 2400 quadros a 48 kHz)."""
    passo = max(1, taxa // ciclo)
    return max(passo, round(hz / passo) * passo)


def _seno_do_ciclo(hz: int, ciclo: int, taxa: int) -> list[float]:
    return [math.sin(2.0 * math.pi * hz * k / taxa) for k in range(ciclo)]


def _ate_o_pico(onda: list[float]) -> list[float]:
    pico = max((abs(v) for v in onda), default=0.0)
    return [v / pico for v in onda] if pico > 0 else onda


def _onda_periodica(onda: str, hz: int, ciclo: int, taxa: int) -> list[float]:
    """A onda do jogo na frequência do canal, por cima do seno: ``|onda| >= |seno|``."""
    from hefesto_dualsense4unix.integrations import classe_do_rumble as classes

    seno = _seno_do_ciclo(hz, ciclo, taxa)
    periodo = taxa / hz
    saida: list[float] = []
    for k, s in enumerate(seno):
        sinal = 1.0 if s >= 0 else -1.0
        fase = (k % periodo) / periodo
        if onda == classes.QUADRADA:
            v = sinal
        elif onda == classes.TRIANGULO:
            tri = 1.0 - 4.0 * abs(fase - 0.25) if fase < 0.75 else 4.0 * (fase - 1.0)
            v = sinal * max(abs(s), min(1.0, abs(tri) * math.pi / 2.0))
        elif onda == classes.DENTE_QUE_SOBE:
            v = sinal * max(abs(s), (fase * 2.0) % 1.0)
        elif onda == classes.DENTE_QUE_DESCE:
            v = sinal * max(abs(s), 1.0 - (fase * 2.0) % 1.0)
        else:
            v = s
        saida.append(v)
    return saida


@functools.lru_cache(maxsize=64)
def ciclos_do_timbre(
    chave: str, ciclo: int = 2400, taxa: int = TAXA
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """O ciclo ``(forte, fraco)`` do timbre, de pico 1, na ordem dos canais 3 e 4 do bloco."""
    forte = _seno_do_ciclo(HZ_DO_FORTE, ciclo, taxa)
    fraco = _seno_do_ciclo(HZ_DO_FRACO, ciclo, taxa)
    tipo, _, nome = chave.partition(":")
    if tipo == "golpe":
        forma = FORMAS.get(nome) or ASSINATURAS.get(nome) or FORMAS[TOQUE]
        partes = [(_no_ciclo(hz, ciclo, taxa), peso) for hz, peso in forma.componentes]
        if forma.cauda_hz:
            partes.append((_no_ciclo(forma.cauda_hz, ciclo, taxa), forma.cauda_peso))
        mistura = [0.0] * ciclo
        for hz, peso in partes:
            for k, v in enumerate(_seno_do_ciclo(hz, ciclo, taxa)):
                mistura[k] += peso * v
        forte = fraco = _ate_o_pico(mistura)
    elif tipo == "corpo":
        base = _seno_do_ciclo(CORPO_HZ, ciclo, taxa)
        harmonica = _seno_do_ciclo(3 * CORPO_HZ, ciclo, taxa)
        forte = _ate_o_pico(
            [b + PESO_DA_HARMONICA * h for b, h in zip(base, harmonica, strict=True)]
        )
    elif tipo == "grao":  # (noqa-acento): chave
        a_cada = max(1, taxa // GRAOS_DO_TIMBRE_POR_S)
        largura = max(2, taxa * GRAO_DO_TIMBRE_MS // 1000)
        grao = [  # (noqa-acento): variável
            math.sin(math.pi * (k % a_cada) / largura) if k % a_cada < largura else 0.0
            for k in range(ciclo)
        ]
        fraco = [
            max(-1.0, min(1.0, s * (1.0 + GANHO_DO_GRAO_DO_TIMBRE * g)))
            for s, g in zip(fraco, grao, strict=True)
        ]
    elif tipo == "periodico":
        forte = _onda_periodica(nome, HZ_DO_FORTE, ciclo, taxa)
        fraco = _onda_periodica(nome, HZ_DO_FRACO, ciclo, taxa)
    return tuple(forte), tuple(fraco)


__all__ = [
    "APARO",
    "ASSINATURAS",
    "CONTINUAS",
    "CORPO_HZ",
    "CORTE_ALTO_HZ",
    "CORTE_BAIXO_HZ",
    "DICAS",
    "DO_ESTILO",
    "ECO",
    "ESCOLHAS",
    "ESTALO",
    "FORMAS",
    "FORMAS_LONGAS",
    "GANHO_DO_CORPO",
    "GANHO_DO_GRAO_DO_TIMBRE",
    "GRAO",
    "GRAOS_DO_TIMBRE_POR_S",
    "GRAO_DO_TIMBRE_MS",
    "GUARDA",
    "HZ_DO_FORTE",
    "HZ_DO_FRACO",
    "IMPACTO",
    "MOTOR_DE_EPOCA",
    "NOTAS_DA_ASSINATURA",
    "PESO_DA_HARMONICA",
    "POR_ESTILO",
    "ROTULOS",
    "SEM_CORPO",
    "SEM_EFEITO",
    "SEM_GRAO",
    "SEM_TIMBRE",
    "SOM_NO_CORPO",
    "TAXA",
    "TETO_DO_CORPO",
    "TOQUE",
    "FiltroDoCorpo",
    "Forma",
    "GeradorDoGrao",
    "GeradorDoMotorDeEpoca",
    "amostras",
    "ciclos_do_timbre",
    "escolha_valida",
    "forma_da_nota",
    "forma_do_estilo",
    "forma_que_vale",
    "timbre_do_rumble",
]
