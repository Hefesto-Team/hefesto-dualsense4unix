"""A intensidade da cena: o quanto o jogo está calmo, tenso ou em combate, de 0 a 1.

A-INTENSIDADE-DA-CENA-REGE-O-QUE-O-HEFESTO-SOMA-01 (22/10/2026). Puro: os sinais que já chegam
ao tato (a energia do som do jogo, quando o ouvido está aberto, e as bordas do rumble e do dedo)
entram por uma média lenta, a intensidade cai numa de três faixas com histerese e permanência
mínima, e a faixa gradua só o que o Hefesto soma: a força do toque do tiro, do padrão dos motores
e do corpo, e o ritmo da luz que respira. O rumble, a háptica, o gatilho e a luz que o jogo manda
nunca passam por aqui. Uma intensidade por sessão de jogo; a força continua de cada controle.
Sem jogo, e no Nativo e no Personalizado, o fator é 1,0 (o comportamento de antes).
Valores de partida, por delegação, a validar pelo usuário na bancada.
"""
from __future__ import annotations

import math
import threading
from array import array
from collections.abc import Iterable, Mapping
from typing import Any

#: A graduação NÃO age até a prova da bancada: a intensidade se calcula e se expõe no estado do
#: daemon, mas o fator fica em 1,0. Liga quando ``scripts/ensaios/gravar_a_intensidade_da_cena.py``
#: mostrar, em três gêneros, a mediana do combate acima da do calmo nos trechos marcados à mão
#: (sem essa separação a régua vira enfeite). A régua liga por parâmetro (``graduar=True``).
GRADUACAO_LIGADA = False

#: A constante de tempo da média lenta de cada sinal.
CONSTANTE_DE_TEMPO_S = 3.0
#: O tempo mínimo em cada faixa antes de trocar.
PERMANENCIA_MINIMA_S = 4.0
#: O RMS do som do jogo (fração da escala cheia) que conta como som cheio de combate.
ENERGIA_CHEIA = 0.25
#: As bordas por segundo, num controle, que contam como golpe cheio.
RUMBLE_CHEIO_POR_S = 3.0
DEDO_CHEIO_POR_S = 2.0

CALMA = "calma"
TENSA = "tensa"
COMBATE = "combate"
FAIXAS = (CALMA, TENSA, COMBATE)
#: As divisas entre as faixas (calma | tensa | combate) e a folga de cada lado delas.
DIVISAS = (0.25, 0.55)
HISTERESE = 0.05
#: A força do que o Hefesto soma em cada faixa: a base moderada na calma, a força cheia no combate.
FATOR_DA_FAIXA: Mapping[str, float] = {CALMA: 0.6, TENSA: 0.8, COMBATE: 1.0}
#: A faixa em que o jogo começa: a força de antes, até a média dizer outra coisa.
FAIXA_DO_COMECO = COMBATE
#: O ritmo da luz que respira na cena calma (o mais lento da escala de 1 a 10).
RITMO_MAIS_LENTO = 1
#: O jogo decide sozinho no Nativo; o Personalizado é o que a pessoa montou: nenhum dos dois gradua.
ESTILOS_SEM_GRADUACAO = frozenset({"nativo", "personalizado"})

TIPO_RUMBLE = "rumble_tiro"
TIPO_DEDO = "dedo"

_SOMA_DOS_PRODUTOS = getattr(math, "sumprod", None)


def rms_do_pcm(pcm: bytes) -> float:
    """O RMS do PCM do jogo (s16le), em fração da escala cheia; os dois canais juntos."""
    amostras = array("h")
    amostras.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not amostras:
        return 0.0
    if _SOMA_DOS_PRODUTOS is not None:
        soma = float(_SOMA_DOS_PRODUTOS(amostras, amostras))
    else:  # pragma: no cover - Python sem math.sumprod
        soma = float(sum(x * x for x in amostras))
    return math.sqrt(soma / len(amostras)) / 32768.0


def faixa_de(valor: float, atual: str) -> str:
    """A faixa da intensidade ``valor``, com a histerese em volta da faixa ``atual``."""
    baixa, alta = DIVISAS
    indice = FAIXAS.index(atual) if atual in FAIXAS else 1
    sobe = (baixa + HISTERESE, alta + HISTERESE)
    desce = (baixa - HISTERESE, alta - HISTERESE)
    while indice < 2 and valor >= sobe[indice]:
        indice += 1
    while indice > 0 and valor < desce[indice - 1]:
        indice -= 1
    return FAIXAS[indice]


def _media(antes: float, amostra: float, dt: float) -> float:
    alfa = 1.0 - math.exp(-dt / CONSTANTE_DE_TEMPO_S)
    return antes + alfa * (amostra - antes)


class IntensidadeDaCena:
    """A intensidade de uma sessão de jogo, andando no tique do tato.

    ``contar`` recebe os eventos do tique (as bordas), ``ouvir_o_som`` o PCM do jogo (na thread
    do ouvido) e ``andar`` a passagem do tempo. ``fator`` e ``velocidade_da_luz`` são o que a
    faixa faz com o que o Hefesto soma; com ``graduar`` desligado os dois dão 1,0.
    """

    def __init__(self, graduar: bool = GRADUACAO_LIGADA) -> None:
        self.graduar = graduar
        self._trava = threading.Lock()
        self._som: tuple[float, int] = (0.0, 0)
        self._bordas: dict[str, dict[str, int]] = {TIPO_RUMBLE: {}, TIPO_DEDO: {}}
        self.totais: dict[str, int] = {TIPO_RUMBLE: 0, TIPO_DEDO: 0}
        self.esquecer()

    def esquecer(self) -> None:
        """Sem jogo: a sessão acabou, e a seguinte começa do zero."""
        self.jogo = False
        self.ouvido = False
        self.faixa: str | None = None
        self._desde = 0.0
        self._antes: float | None = None
        self.energia = 0.0
        self.som_cru = 0.0
        self._taxas: dict[str, dict[str, float]] = {TIPO_RUMBLE: {}, TIPO_DEDO: {}}
        #: as bordas que esta sessão já mostrou: o jogo sem rumble, ou em que a mão não usa o
        #: gatilho, não fica preso na calma por um sinal que ele nunca dá
        self.vistos: set[str] = set()
        with self._trava:
            self._som = (0.0, 0)
        for contagem in self._bordas.values():
            contagem.clear()

    # --- os sinais ---

    def contar(self, eventos: Iterable[Any]) -> None:
        """As bordas do rumble e do dedo deste tique, controle a controle."""
        for evento in eventos:
            tipo = getattr(evento, "tipo", None)
            if not isinstance(tipo, str) or tipo not in self._bordas:
                continue
            contagem = self._bordas[tipo]
            uniq = str(getattr(evento, "uniq", ""))
            contagem[uniq] = contagem.get(uniq, 0) + 1
            self.totais[tipo] += 1
            self.vistos.add(tipo)

    def ouvir_o_som(self, pcm: bytes) -> None:
        """Um pedaço do PCM do jogo (thread do ouvido): soma o quadrado do RMS até o tique."""
        rms = rms_do_pcm(pcm)
        with self._trava:
            soma, n = self._som
            self._som = (soma + rms * rms, n + 1)

    # --- o tempo ---

    def andar(self, agora: float, *, jogo: bool, ouvido: bool, uniqs: Iterable[str] = ()) -> None:
        """Um tique: as médias lentas andam e a faixa troca, se a média e a permanência deixam."""
        if not jogo:
            if self.jogo:
                self.esquecer()
            for contagem in self._bordas.values():
                contagem.clear()
            return
        if not self.jogo:
            self.jogo = True
            self.faixa = FAIXA_DO_COMECO
            self._desde = agora
            self._antes = agora
        self.ouvido = bool(ouvido)
        with self._trava:
            soma, n = self._som
            self._som = (0.0, 0)
        if n:
            self.som_cru = math.sqrt(soma / n)
        dt = agora - (self._antes if self._antes is not None else agora)
        self._antes = agora
        mesa = set(uniqs)
        if dt > 0:
            if self.ouvido:
                self.energia = _media(self.energia, min(1.0, self.som_cru / ENERGIA_CHEIA), dt)
            for tipo, contagem in self._bordas.items():
                taxas = self._taxas[tipo]
                for uniq in mesa | set(contagem) | set(taxas):
                    taxas[uniq] = _media(taxas.get(uniq, 0.0), contagem.get(uniq, 0) / dt, dt)
                for saiu in [u for u in taxas if u not in mesa and u not in contagem]:
                    if taxas[saiu] < 1e-3:
                        del taxas[saiu]
        for contagem in self._bordas.values():
            contagem.clear()
        atual = self.faixa or FAIXA_DO_COMECO
        valor = self.intensidade
        if valor is None:
            return  # nenhum sinal na sessão ainda: a cena não se sabe, a faixa fica
        nova = faixa_de(valor, atual)
        if nova != atual and agora - self._desde >= PERMANENCIA_MINIMA_S:
            self.faixa = nova
            self._desde = agora

    # --- a leitura ---

    def por_segundo(self, tipo: str) -> float:
        """As bordas por segundo do controle mais intenso (a cena é a do mais agitado)."""
        return max(self._taxas.get(tipo, {}).values(), default=0.0)

    @property
    def intensidade(self) -> float | None:
        """A média dos sinais normalizados que a sessão tem: a energia só com o ouvido aberto,
        cada borda só depois da primeira; ``None`` sem sinal nenhum."""
        cheio = {TIPO_RUMBLE: RUMBLE_CHEIO_POR_S, TIPO_DEDO: DEDO_CHEIO_POR_S}
        sinais = [min(1.0, self.por_segundo(tipo) / cheio[tipo])
                  for tipo in (TIPO_RUMBLE, TIPO_DEDO) if tipo in self.vistos]
        if self.ouvido:
            sinais.append(self.energia)
        return sum(sinais) / len(sinais) if sinais else None

    def _gradua(self, estilo: Any) -> bool:
        return (self.graduar and self.jogo and self.faixa is not None
                and isinstance(estilo, str) and bool(estilo)
                and estilo not in ESTILOS_SEM_GRADUACAO)

    def fator(self, estilo: Any) -> float:
        """A força do que o Hefesto soma agora (0,6 a 1,0); 1,0 sem graduar, sem jogo ou fora."""
        if not self._gradua(estilo) or self.faixa is None:
            return 1.0
        return float(FATOR_DA_FAIXA[self.faixa])

    def velocidade_da_luz(self, ritmo: int, estilo: Any) -> float:
        """O quanto a luz que respira anda: do ritmo mais lento (calma) ao do efeito (combate).

        O período do respirar é inverso ao ritmo, então andar a ``alvo / ritmo`` do relógio é
        respirar no ritmo ``alvo``; nunca acima de 1,0, nunca mais rápido que o efeito.
        """
        if not self._gradua(estilo) or self.faixa is None:
            return 1.0
        ritmo = max(RITMO_MAIS_LENTO, int(ritmo))
        alvo = {CALMA: float(RITMO_MAIS_LENTO), TENSA: (RITMO_MAIS_LENTO + ritmo) / 2.0,
                COMBATE: float(ritmo)}[self.faixa]
        return min(1.0, alvo / ritmo)

    def estado(self, estilo: Any = None) -> dict[str, Any]:
        """O que a bancada lê ao vivo: os sinais, a intensidade, a faixa e o fator."""
        return {
            "jogo": self.jogo,
            "ouvido": self.ouvido,
            "graduando": self.graduar,
            "intensidade": None if self.intensidade is None else round(self.intensidade, 4),
            "faixa": self.faixa,
            "fator": self.fator(estilo),
            "energia": round(self.energia, 4),
            "som_cru": round(self.som_cru, 5),
            "rumble_por_s": round(self.por_segundo(TIPO_RUMBLE), 3),
            "dedo_por_s": round(self.por_segundo(TIPO_DEDO), 3),
            "bordas_do_rumble": self.totais[TIPO_RUMBLE],
            "bordas_do_dedo": self.totais[TIPO_DEDO],
        }


def estado_do_daemon(daemon: Any) -> dict[str, Any] | None:
    """O bloco ``intensidade_da_cena`` do ``daemon.state_full``; ``None`` sem o motor do tato."""
    motor = getattr(daemon, "_tato_vivo", None)
    cena = getattr(motor, "cena", None)
    if not isinstance(cena, IntensidadeDaCena):
        return None
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import estilo_ativo

    return {"ligado": bool(getattr(motor, "ligado", False)),
            **cena.estado(estilo_ativo(daemon))}


__all__ = [
    "CALMA",
    "COMBATE",
    "CONSTANTE_DE_TEMPO_S",
    "DIVISAS",
    "ESTILOS_SEM_GRADUACAO",
    "FAIXAS",
    "FATOR_DA_FAIXA",
    "GRADUACAO_LIGADA",
    "PERMANENCIA_MINIMA_S",
    "RITMO_MAIS_LENTO",
    "TENSA",
    "IntensidadeDaCena",
    "estado_do_daemon",
    "faixa_de",
    "rms_do_pcm",
]
