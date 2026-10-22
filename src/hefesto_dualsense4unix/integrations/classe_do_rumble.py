"""A classe do rumble do jogo Xbox pela linha do tempo do par ``(fraco, forte)`` (funções puras).

O ``replay.length`` não diz a duração: o SDL2 manda sempre ``SDL_MAX_RUMBLE_DURATION_MS`` e cala
com um rumble ``(0, 0)`` depois; o Wine manda o menor ``cutoff_time_ms`` (1000 ms de partida).
A classe sai do que se vê: quanto subiu, quanto durou, qual motor domina. O ``FF_PERIODIC`` traz
a onda do jogo, a única pista de timbre que ele dá. Os limites são valores de partida, a validar
na bancada (O-RUMBLE-DO-JOGO-XBOX-GANHA-O-TIMBRE-DO-ESTILO-01).
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass

GOLPE = "golpe"
MEDIO = "medio"  # (noqa-acento): chave
CONTINUO_GRAVE = "continuo_grave"
CONTINUO_FINO = "continuo_fino"
PERIODICO = "periodico"

#: As classes, na ordem em que o instrumento as conta.
CLASSES: tuple[str, ...] = (GOLPE, MEDIO, CONTINUO_GRAVE, CONTINUO_FINO, PERIODICO)

#: Sobe e cai em até 150 ms: um golpe (o tiro, a pancada).
GOLPE_ATE_S = 0.150
#: Dura mais que 400 ms: um contínuo (o motor, a chuva, o terremoto). Entre os dois, o médio.
CONTINUO_DESDE_S = 0.400
#: Abaixo deste nível (0 a 255) nos dois motores, o jogo está calado.
NIVEL_MINIMO = 8
#: Quantos trechos a linha do tempo guarda para o instrumento (a classe, a duração e o pico).
TRECHOS_GUARDADOS = 32

SENO = "seno"
QUADRADA = "quadrada"
TRIANGULO = "triangulo"
DENTE_QUE_SOBE = "dente_que_sobe"
DENTE_QUE_DESCE = "dente_que_desce"
ONDAS: tuple[str, ...] = (SENO, QUADRADA, TRIANGULO, DENTE_QUE_SOBE, DENTE_QUE_DESCE)


@dataclass(frozen=True)
class FormaDoPeriodico:
    """O que o jogo disse de um ``FF_PERIODIC``: a onda, o período e o envelope, em ms e 0-255."""

    onda: str
    periodo_ms: int = 0
    ataque_ms: int = 0
    nivel_do_ataque: int = 0
    queda_ms: int = 0
    nivel_da_queda: int = 0


def onda_do_codigo(codigo: int, ecodes: object) -> str:
    """A onda de um ``waveform`` do kernel; o seno quando o código não é um dos que se conhece."""
    nomes = (
        ("FF_SQUARE", QUADRADA),
        ("FF_TRIANGLE", TRIANGULO),
        ("FF_SINE", SENO),
        ("FF_SAW_UP", DENTE_QUE_SOBE),
        ("FF_SAW_DOWN", DENTE_QUE_DESCE),
    )
    for nome, onda in nomes:
        if getattr(ecodes, nome, None) == codigo:
            return onda
    return SENO


def calado(fraco: int, forte: int) -> bool:
    """Os dois motores abaixo do mínimo: o jogo não está vibrando."""
    return max(int(fraco), int(forte)) < NIVEL_MINIMO


def _dominio(fraco: int, forte: int) -> str:
    return CONTINUO_GRAVE if int(forte) >= int(fraco) else CONTINUO_FINO


def classe_do_trecho(
    duracao_s: float, fraco: int, forte: int, onda: str | None = None
) -> str:
    """A classe de um trecho que já acabou: subiu, durou ``duracao_s`` com os picos dados, caiu."""
    if onda is not None:
        return PERIODICO
    if duracao_s <= GOLPE_ATE_S:
        return GOLPE
    if duracao_s <= CONTINUO_DESDE_S:
        return MEDIO
    return _dominio(fraco, forte)


def classe_viva(
    desde_s: float, fraco: int, forte: int, onda: str | None = None
) -> str | None:
    """A classe do que toca agora, ``desde_s`` depois da subida; ``None`` com o jogo calado.

    O golpe é presumido até 150 ms: quem sobe ainda não disse quanto vai durar, e o golpe é o
    que mais pede forma. Depois, o médio; passados 400 ms, o contínuo do motor que domina agora.
    """
    if calado(fraco, forte):
        return None
    if onda is not None:
        return PERIODICO
    if desde_s <= GOLPE_ATE_S:
        return GOLPE
    if desde_s <= CONTINUO_DESDE_S:
        return MEDIO
    return _dominio(fraco, forte)


class LinhaDoTempo:
    """A linha do tempo do rumble de UM controle: o trecho em curso e quantos de cada classe."""

    def __init__(self) -> None:
        self._inicio: float | None = None
        self._pico = (0, 0)
        self._onda: str | None = None
        self.contagem: dict[str, int] = dict.fromkeys(CLASSES, 0)
        #: os últimos trechos que caíram: ``(classe, duração em ms, fraco, forte)``
        self.ultimos: deque[tuple[str, int, int, int]] = deque(maxlen=TRECHOS_GUARDADOS)

    @property
    def inicio(self) -> float | None:
        """Quando o trecho em curso subiu; ``None`` com o jogo calado."""
        return self._inicio

    def anotar(
        self, t: float, fraco: int, forte: int, onda: str | None = None
    ) -> str | None:
        """O par novo em ``t``. Devolve a classe do trecho que acabou de cair, ou ``None``."""
        if calado(fraco, forte):
            if self._inicio is None:
                return None
            classe = classe_do_trecho(t - self._inicio, *self._pico, onda=self._onda)
            self.contagem[classe] += 1
            self.ultimos.append((classe, round((t - self._inicio) * 1000), *self._pico))
            self._inicio, self._pico, self._onda = None, (0, 0), None
            return classe
        if self._inicio is None:
            self._inicio = t
        self._pico = (max(self._pico[0], int(fraco)), max(self._pico[1], int(forte)))
        if onda is not None:
            self._onda = onda
        return None

    def classe(self, t: float, fraco: int, forte: int, onda: str | None = None) -> str | None:
        """A classe viva em ``t`` para o par de agora."""
        if self._inicio is None:
            return None
        return classe_viva(t - self._inicio, fraco, forte, onda)

    def contagem_copiada(self) -> Mapping[str, int]:
        return dict(self.contagem)


__all__ = [
    "CLASSES",
    "CONTINUO_DESDE_S",
    "CONTINUO_FINO",
    "CONTINUO_GRAVE",
    "DENTE_QUE_DESCE",
    "DENTE_QUE_SOBE",
    "GOLPE",
    "GOLPE_ATE_S",
    "MEDIO",
    "NIVEL_MINIMO",
    "ONDAS",
    "PERIODICO",
    "QUADRADA",
    "SENO",
    "TRECHOS_GUARDADOS",
    "TRIANGULO",
    "FormaDoPeriodico",
    "LinhaDoTempo",
    "calado",
    "classe_do_trecho",
    "classe_viva",
    "onda_do_codigo",
]
