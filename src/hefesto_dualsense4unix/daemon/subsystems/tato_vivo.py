"""O tato vivo: o motor que reage ao tiro, e só fala onde o jogo cala.

O-TATO-VIVO-SO-FALA-ONDE-O-JOGO-CALA-01 (08/10/2026). No PS5 cada sensação do
tiro é um canal que o jogo escreve no instante do tiro. No PC, quando o jogo
não fala DualSense (ou fala e não escreve aquele canal), ninguém escrevia nada
por EVENTO: o daemon só tinha caminhos por ESTADO. Este módulo é o caminho por
evento, com uma regra só para todos os canais:

* **o jogo manda, o controle obedece** (ordem de 29/09): ``decidir`` é a
  política pura sobre os carimbos do pad virtual e o relógio; o motor só
  escreve no canal em que o jogo está calado;
* **teto de pulsos**: 12 por segundo por controle e 40 no total;
* **volta ao perfil**: todo valor escrito tem prazo, e o tique devolve o canal
  quando o prazo vence (ou solta sem devolver, se o jogo passou a mandar);
* **por controle**: cada evento leva o ``uniq`` do controle que o gerou, e os
  atuadores escrevem só pelas APIs por ``uniq`` do backend (P1 a P4, cabo e
  rádio pelo mesmo caminho, nunca broadcast);
* **Modo Nativo calado**: sem pad virtual o jogo fala com o aparelho de
  verdade, e o motor não tem o que dizer;
* **nasce desligado**: liga só quando a receita do perfil ativo pede alguma
  reação: a do estilo que ele guarda (``Profile.estilo``), traduzida por
  :func:`receita_do_estilo`, com o desvio da bancada (``receita_do_tato``) por
  cima, campo a campo.

Os efeitos de cada canal são os atuadores, que entram por sprint em cima deste
núcleo. O estado de diagnóstico (contadores) mora em ``daemon._tato_vivo``.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Any, Protocol

from hefesto_dualsense4unix.daemon.lifecycle import (
    MODO_DUALSENSE,
    MODO_NATIVO,
    MODO_XBOX,
    modo_do_pad,
    o_hefesto_fala_no_modo,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

CANAL_GATILHO = "gatilho"
CANAL_LUZ = "luz"
CANAL_HAPTICA = "haptica"
CANAL_SOM = "som"
CANAIS = (CANAL_GATILHO, CANAL_LUZ, CANAL_HAPTICA, CANAL_SOM)

# Gatilho e luz são ESTADO: o valor que o jogo pôs fica na camada do jogo pela
# sessão inteira (a arma troca uma vez, o gatilho fica). Háptica e som são
# FLUXO: o jogo fala enquanto toca, e calar por 3 s é calar.
CANAIS_DE_ESTADO = frozenset({CANAL_GATILHO, CANAL_LUZ})

# O carimbo do pad virtual que diz «o jogo escreveu neste canal»
# (`integrations/uhid_gamepad.py`, `ATIVIDADE_*`). A háptica do jogo DualSense
# viaja como áudio; o rumble que o jogo pede é SINAL para o motor, não veto.
_CARIMBO_DO_CANAL: dict[str, str] = {
    CANAL_GATILHO: "trigger",
    CANAL_LUZ: "lightbar",
    CANAL_HAPTICA: "audio_do_jogo",
    CANAL_SOM: "audio_do_jogo",
}


JANELA_DO_JOGO_S = 3.0
TETO_POR_CONTROLE = 12
TETO_TOTAL = 40
JANELA_DO_TETO_S = 1.0
INTERVALO_S = 1.0 / 60.0
RELEITURA_DA_RECEITA_S = 1.0

CAMPO_DA_RECEITA = "receita_do_tato"

TIPO_DEDO = "dedo"
TIPO_RUMBLE = "rumble_tiro"
TIPO_SOM = "som_tiro"

LADO_ESQUERDO = "esquerdo"
LADO_DIREITO = "direito"
LADO_CENTRO = "centro"

REACOES_DA_LUZ = ("parada", "pulsa", "evento")


@dataclass(frozen=True)
class EstadoDoCanal:
    """O que a política precisa saber de UM controle, num instante."""

    modo: str
    visto_ha_s: Mapping[str, float] = field(default_factory=dict)
    sessao_aberta: bool = False
    ha_jogo: bool = False
    # Há quanto tempo a sessão de agora abriu; ``None`` quando não se viu abrir.
    sessao_ha_s: float | None = None


# O `visto_ha_s` do pad vem arredondado a 0,1 s, e a abertura se vê um tique depois.
FOLGA_DA_SESSAO_S = 0.25


def _da_sessao(idade: float | None, estado: EstadoDoCanal) -> bool:
    """O carimbo é desta sessão. O de uma sessão que já fechou não vale mais."""
    if idade is None:
        return False
    if estado.sessao_ha_s is None:
        return True
    return idade <= estado.sessao_ha_s + FOLGA_DA_SESSAO_S


def _o_modo_cala_o_motor(estado: EstadoDoCanal) -> bool:
    """Sem jogo, ou num modo em que o Hefesto não fala (o dono do modo decide)."""
    return not estado.ha_jogo or not o_hefesto_fala_no_modo(estado.modo)


def decidir(canal: str, estado: EstadoDoCanal) -> bool:
    """``True`` quando o jogo cala neste canal e o motor pode escrever."""
    if _o_modo_cala_o_motor(estado):
        return False
    carimbo = _CARIMBO_DO_CANAL.get(canal)
    if carimbo is None:
        return False
    idade = estado.visto_ha_s.get(carimbo)
    if idade is not None and idade < JANELA_DO_JOGO_S:
        return False
    if canal in CANAIS_DE_ESTADO and estado.sessao_aberta:
        # Escreveu há mais de 3 s: no fluxo é silêncio; no estado, o valor dele
        # segue valendo enquanto a sessão do jogo estiver aberta.
        # O fecho do pad devolve a sessão, mas guarda o carimbo: só o desta conta.
        if _da_sessao(idade, estado):
            return False
        # A volta do backend é a sessão inteira (`end_game_session_for`): se o
        # jogo pintou o OUTRO canal de estado, devolver este apagaria o dele.
        for outro in CANAIS_DE_ESTADO - {canal}:
            if _da_sessao(estado.visto_ha_s.get(_CARIMBO_DO_CANAL[outro]), estado):
                return False
    return True


@dataclass(frozen=True)
class Evento:
    """Um tiro (ou o que parece um): de quem, quando, de que lado e com que força."""

    instante: float
    uniq: str
    tipo: str
    lado: str = LADO_CENTRO
    energia: float = 1.0
    #: o recorte do estalo (O-SOM-DO-TIRO-SAI-TAMBEM-NO-CONTROLE-01), que se completa depois.
    recorte: Any = field(default=None, compare=False)


def _limitar(valor: Any, baixo: float, alto: float, padrao: float) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if numero != numero:  # NaN
        return padrao
    return min(alto, max(baixo, numero))


@dataclass(frozen=True)
class Receita:
    """A receita invisível do estilo: o que cada canal faz a cada tiro."""

    vibracao_por_tiro: bool = False
    forca_do_toque: float = 0.6
    duracao_do_toque_ms: int = 40
    gatilho_no_ritmo: bool = False
    frequencia_da_rajada_hz: int = 20
    reacao_ao_tiro: str = "parada"
    cor_do_evento: tuple[int, int, int] | None = None
    lado_do_som: bool = False
    som_no_controle: bool = False

    @property
    def ligada(self) -> bool:
        return (
            self.vibracao_por_tiro
            or self.gatilho_no_ritmo
            or self.reacao_ao_tiro != "parada"
            or self.lado_do_som
            or self.som_no_controle
        )

    @classmethod
    def de(cls, cru: Any) -> Receita:
        """Lê a receita de um dicionário ou objeto, tolerante e com os limites."""
        if cru is None:
            return DESLIGADA
        if isinstance(cru, Receita):
            return cru

        def campo(nome: str, padrao: Any) -> Any:
            if isinstance(cru, Mapping):
                return cru.get(nome, padrao)
            return getattr(cru, nome, padrao)

        reacao = campo("reacao_ao_tiro", "parada")
        if reacao not in REACOES_DA_LUZ:
            reacao = "parada"
        cor_crua = campo("cor_do_evento", None)
        cor: tuple[int, int, int] | None = None
        if isinstance(cor_crua, (list, tuple)) and len(cor_crua) == 3:
            cor = (
                int(_limitar(cor_crua[0], 0, 255, 255)),
                int(_limitar(cor_crua[1], 0, 255, 255)),
                int(_limitar(cor_crua[2], 0, 255, 255)),
            )
        return cls(
            vibracao_por_tiro=bool(campo("vibracao_por_tiro", False)),
            forca_do_toque=_limitar(campo("forca_do_toque", 0.6), 0.0, 1.0, 0.6),
            duracao_do_toque_ms=int(
                _limitar(campo("duracao_do_toque_ms", 40), 25, 60, 40)
            ),
            gatilho_no_ritmo=bool(campo("gatilho_no_ritmo", False)),
            frequencia_da_rajada_hz=int(
                _limitar(campo("frequencia_da_rajada_hz", 20), 5, 40, 20)
            ),
            reacao_ao_tiro=str(reacao),
            cor_do_evento=cor,
            lado_do_som=bool(campo("lado_do_som", False)),
            som_no_controle=bool(campo("som_no_controle", False)),
        )


DESLIGADA = Receita()

#: As variáveis do motor, na ordem: o vocabulário que o desvio da bancada aceita.
CAMPOS_DA_RECEITA: tuple[str, ...] = tuple(f.name for f in fields(Receita))

# O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01 (09/10/2026): a receita do estilo
# (`profiles/estilos_de_jogo.Receita`, a que a tela não mostra) nasceu noutro
# conjunto, com outro vocabulário. A ponte entre as duas línguas mora aqui, e
# cada número tem nome, e cada um é valor de partida.
#: A força do toque pelo degrau de vibração do estilo (`Estilo.vibracao`).
FORCA_DO_DEGRAU: dict[str, float] = {"max": 1.0, "balanceado": 0.6, "economia": 0.35}
#: A luz do estilo que respira ou pisca pulsa a cada tiro; a parada não reage.
REACAO_DA_LUZ_DO_ESTILO: dict[str, str] = {
    "parada": "parada",
    "respira": "pulsa",
    "pisca": "pulsa",
}
#: Os estilos de arma de rajada: só neles o gatilho acompanha o ritmo do tiro.
ESTILOS_DE_RAJADA = frozenset({"fps"})
#: O estalo do tiro no alto-falante do controle nasce desligado em todo estilo.
SOM_NO_CONTROLE_DO_ESTILO = False


def receita_do_estilo(estilo: Any) -> Receita:
    """A receita do motor para um ``Estilo`` de ``estilos_de_jogo``: a tradução."""
    invisivel = getattr(estilo, "receita_invisivel", None)
    if invisivel is None:
        return DESLIGADA
    return Receita(
        vibracao_por_tiro=bool(invisivel.toque_por_tiro),
        forca_do_toque=FORCA_DO_DEGRAU.get(estilo.vibracao, DESLIGADA.forca_do_toque),
        gatilho_no_ritmo=estilo.chave in ESTILOS_DE_RAJADA,
        reacao_ao_tiro=REACAO_DA_LUZ_DO_ESTILO.get(invisivel.luz, DESLIGADA.reacao_ao_tiro),
        lado_do_som=bool(invisivel.lado_do_som),
        som_no_controle=SOM_NO_CONTROLE_DO_ESTILO,
    )


def receita_do_perfil(perfil: Any) -> Receita:
    """A receita do estilo que o perfil guarda, com o desvio dele por cima."""
    if perfil is None:
        return DESLIGADA

    def ler(alvo: Any, nome: str) -> Any:
        if isinstance(alvo, Mapping):
            return alvo.get(nome)
        return getattr(alvo, nome, None)

    base = DESLIGADA
    chave = ler(perfil, "estilo")
    if isinstance(chave, str):
        from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

        estilo = POR_CHAVE.get(chave)
        if estilo is not None:
            base = receita_do_estilo(estilo)
    desvio = ler(perfil, CAMPO_DA_RECEITA)
    if not isinstance(desvio, Mapping):
        return base
    try:
        return Receita.de({**asdict(base), **desvio})
    except Exception:
        logger.debug("tato_vivo_receita_ilegivel", exc_info=True)
        return base


class Teto:
    """Janela deslizante: no máximo N pulsos por controle e M no total, por segundo."""

    def __init__(
        self,
        por_controle: int = TETO_POR_CONTROLE,
        total: int = TETO_TOTAL,
        janela_s: float = JANELA_DO_TETO_S,
    ) -> None:
        self.por_controle = por_controle
        self.total = total
        self.janela_s = janela_s
        self._por_uniq: dict[str, deque[float]] = {}
        self._todos: deque[float] = deque()

    def _podar(self, fila: deque[float], agora: float) -> None:
        while fila and agora - fila[0] >= self.janela_s:
            fila.popleft()

    def cabe(self, uniq: str, agora: float) -> bool:
        self._podar(self._todos, agora)
        do_controle = self._por_uniq.setdefault(uniq, deque())
        self._podar(do_controle, agora)
        return len(do_controle) < self.por_controle and len(self._todos) < self.total

    def gastar(self, uniq: str, agora: float) -> None:
        self._por_uniq.setdefault(uniq, deque()).append(agora)
        self._todos.append(agora)


class Atuador(Protocol):
    """Um canal que reage a eventos. Escreve só no controle do evento."""

    canal: str

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        """Este evento, sob esta receita, pede algo deste canal?"""

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        """Escreve e devolve o prazo da volta ao perfil (``None``: nada a devolver)."""

    def devolver(self, uniq: str, agora: float) -> None:
        """Devolve o canal deste controle ao valor do perfil."""


class TatoVivo:
    """A fila de eventos, a política, o teto e a volta. Sem efeito próprio."""

    def __init__(
        self,
        atuadores: Iterable[Atuador] = (),
        *,
        teto: Teto | None = None,
    ) -> None:
        self.atuadores: list[Atuador] = list(atuadores)
        self.teto = teto if teto is not None else Teto()
        self._fila: deque[Evento] = deque(maxlen=512)
        self._lock = threading.Lock()
        self._pendentes: dict[tuple[str, str], float] = {}
        self.contadores: dict[str, int] = {
            "eventos": 0,
            "escritas": 0,
            "devolucoes": 0,
            "soltos_ao_jogo": 0,
            "recusas_do_jogo": 0,
            "recusas_do_modo": 0,
            "recusas_do_teto": 0,
        }
        self.ligado = False
        self.borda_do_rumble = BordaDoRumble()
        self.borda_do_dedo = BordaDoDedo()
        #: o ouvido do som do jogo (O-TIRO-VEM-DO-LADO-CERTO-01); ``None`` até a receita pedir.
        self.ouvido: Any = None

    def anotar(self, evento: Evento) -> None:
        """Põe um evento na fila. Chamável de qualquer thread."""
        with self._lock:
            self._fila.append(evento)
            self.contadores["eventos"] += 1

    def segurando(self, canal: str) -> frozenset[str]:
        """Os controles em que ``canal`` ainda espera a volta ao perfil (o pulso no ar)."""
        return frozenset(uniq for uniq, dele in self._pendentes if dele == canal)

    def _atuador(self, canal: str) -> Atuador | None:
        for atuador in self.atuadores:
            if atuador.canal == canal:
                return atuador
        return None

    def tique(
        self,
        agora: float,
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        """Devolve o que venceu, decide cada evento da fila e escreve. Retorna as escritas."""
        with self._lock:
            eventos = list(self._fila)
            self._fila.clear()
        for atuador in self.atuadores:
            # O atuador que olha o tique inteiro (o ritmo do gatilho) ouve antes de
            # responder: os dois lados de um controle no mesmo tique viram uma escrita.
            ouvir = getattr(atuador, "ouvir", None)
            if callable(ouvir):
                ouvir(eventos, receita)
        for (uniq, canal), prazo in list(self._pendentes.items()):
            estado = estado_de(uniq)
            if estado is not None and not decidir(canal, estado):
                # O jogo passou a mandar (ou o modo mudou): o valor agora é dele.
                del self._pendentes[(uniq, canal)]
                self.contadores["soltos_ao_jogo"] += 1
                soltar = getattr(self._atuador(canal), "soltar", None)
                if callable(soltar):
                    soltar(uniq)
                continue
            if agora >= prazo:
                self._devolver(uniq, canal, agora)
        escritas = 0
        for evento in eventos:
            estado = estado_de(evento.uniq)
            if estado is None:
                continue
            self._prolongar(evento, receita, agora)
            pedem = [a for a in self.atuadores if a.responde_a(evento, receita)]
            if not pedem:
                continue
            livres = [a for a in pedem if decidir(a.canal, estado)]
            if not livres:
                chave = (
                    "recusas_do_modo" if _o_modo_cala_o_motor(estado) else "recusas_do_jogo"
                )
                self.contadores[chave] += 1
                continue
            if not self.teto.cabe(evento.uniq, agora):
                self.contadores["recusas_do_teto"] += 1
                continue
            self.teto.gastar(evento.uniq, agora)
            for atuador in livres:
                try:
                    volta = atuador.escrever(evento, receita, agora)
                except Exception:
                    logger.debug("tato_vivo_escrita_falhou", canal=atuador.canal,
                                 exc_info=True)
                    continue
                escritas += 1
                self.contadores["escritas"] += 1
                if volta is not None:
                    chave_p = (evento.uniq, atuador.canal)
                    self._pendentes[chave_p] = max(
                        volta, self._pendentes.get(chave_p, volta)
                    )
        return escritas

    def _prolongar(self, evento: Evento, receita: Receita, agora: float) -> None:
        """O canal que segue valendo enquanto o tiro continua empurra a volta."""
        for atuador in self.atuadores:
            chave = (evento.uniq, atuador.canal)
            prolongar = getattr(atuador, "prolongar", None)
            if chave not in self._pendentes or not callable(prolongar):
                continue
            novo = prolongar(evento, receita, agora)
            if novo is not None:
                self._pendentes[chave] = max(novo, self._pendentes[chave])

    def _devolver(self, uniq: str, canal: str, agora: float) -> None:
        self._pendentes.pop((uniq, canal), None)
        atuador = self._atuador(canal)
        if atuador is None:
            return
        try:
            atuador.devolver(uniq, agora)
        except Exception:
            logger.debug("tato_vivo_devolucao_falhou", canal=canal, exc_info=True)
            return
        self.contadores["devolucoes"] += 1

    def parar(self, agora: float | None = None) -> None:
        """Devolve tudo o que está preso e esvazia a fila."""
        instante = time.monotonic() if agora is None else agora
        with self._lock:
            self._fila.clear()
        for uniq, canal in list(self._pendentes):
            self._devolver(uniq, canal, instante)

    @property
    def pendentes(self) -> dict[tuple[str, str], float]:
        return dict(self._pendentes)

    def estado(self) -> dict[str, Any]:
        """Diagnóstico: contadores e se o motor está ligado. Nunca texto de tela."""
        return {
            "ligado": self.ligado,
            "pendentes": len(self._pendentes),
            **self.contadores,
        }


# --- As fontes de evento -------------------------------------------------


DEDO_DISPARA = 160
DEDO_SOLTA = 96


class BordaDoDedo:
    """O dedo que aperta o gatilho: um evento por aperto, com histerese."""

    def __init__(self, dispara: int = DEDO_DISPARA, solta: int = DEDO_SOLTA) -> None:
        self.dispara = dispara
        self.solta = solta
        self._apertado: dict[tuple[str, str], bool] = {}
        self._apertou_em: dict[str, float] = {}

    def ver(self, uniq: str, l2: int, r2: int, agora: float) -> list[Evento]:
        eventos: list[Evento] = []
        for lado, valor in ((LADO_ESQUERDO, l2), (LADO_DIREITO, r2)):
            chave = (uniq, lado)
            apertado = self._apertado.get(chave, False)
            if not apertado and valor >= self.dispara:
                self._apertado[chave] = True
                self._apertou_em[uniq] = agora
                eventos.append(
                    Evento(agora, uniq, TIPO_DEDO, lado, min(1.0, valor / 255.0))
                )
            elif apertado and valor <= self.solta:
                self._apertado[chave] = False
        return eventos

    def apertado(self, uniq: str, lado: str) -> bool:
        return self._apertado.get((uniq, lado), False)

    def atirando(self, uniq: str, instante: float) -> bool:
        """O dedo deste controle segura um gatilho, ou apertou há pouco."""
        if any(self.apertado(uniq, lado) for lado in (LADO_ESQUERDO, LADO_DIREITO)):
            return True
        apertou = self._apertou_em.get(uniq)
        return apertou is not None and -MESMO_TIRO_S <= instante - apertou <= JANELA_DO_DISPARO_S


# A-VIBRACAO-FINA-BATE-A-CADA-TIRO-01: a borda do rumble que o jogo pede.
# Um tiro por BORDA, nunca por nível: o pedido repetido igual (o `cosmic-osk`
# manda vibração nula a ~20 por segundo por pad) e o nível sustentado não são
# borda. Os limiares são de partida.
RUMBLE_DISPARA = 80
RUMBLE_SUBIDA = 64
RUMBLE_REARMA = 48
RUMBLE_JUNTA_S = 0.03  # a rampa de um tiro só (0 → 100 → 200 em 8 ms)


class BordaDoRumble:
    """O par ``(fraco, forte)`` do jogo, controle a controle: um evento por subida.

    A borda e o lado vêm do pedido CRU do jogo; a barra de intensidade dela só
    entra na energia (``efetivo``). O jogo manda, e o ajuste do Hefesto só
    potencializa, nunca veta: com a barra a 50 % o tiro de 150 continua tiro.
    """

    def __init__(
        self,
        dispara: int = RUMBLE_DISPARA,
        subida: int = RUMBLE_SUBIDA,
        rearma: int = RUMBLE_REARMA,
        junta_s: float = RUMBLE_JUNTA_S,
    ) -> None:
        self.dispara = dispara
        self.subida = subida
        self.rearma = rearma
        self.junta_s = junta_s
        self._armado: dict[str, bool] = {}
        self._base: dict[str, int] = {}
        self._pico: dict[str, int] = {}
        self._disparo: dict[str, float] = {}

    def ver(
        self,
        uniq: str,
        fraco: int,
        forte: int,
        agora: float,
        efetivo: tuple[int, int] | None = None,
    ) -> list[Evento]:
        """``fraco``/``forte`` são o pedido cru do jogo; ``efetivo``, o par depois da barra."""
        nivel = max(0, min(255, max(int(fraco), int(forte))))
        if not self._armado.get(uniq, True):
            pico = self._pico.get(uniq, nivel)
            # O tiro por cima de um nível já alto: subiu de novo, fora da rampa do anterior.
            if nivel - pico >= self.subida and agora - self._disparo[uniq] >= self.junta_s:
                return self._disparar(uniq, fraco, forte, nivel, agora, efetivo)
            pico = max(pico, nivel)
            self._pico[uniq] = pico
            if nivel <= self.rearma or pico - nivel >= self.subida:
                self._armado[uniq] = True
                self._base[uniq] = nivel
            return []
        base = min(self._base.get(uniq, 0), nivel)
        self._base[uniq] = base
        if nivel >= self.dispara and nivel - base >= self.subida:
            return self._disparar(uniq, fraco, forte, nivel, agora, efetivo)
        return []

    def _disparar(
        self,
        uniq: str,
        fraco: int,
        forte: int,
        nivel: int,
        agora: float,
        efetivo: tuple[int, int] | None,
    ) -> list[Evento]:
        self._armado[uniq] = False
        self._pico[uniq] = nivel
        self._disparo[uniq] = agora
        if fraco and not forte:
            lado = LADO_DIREITO
        elif forte and not fraco:
            lado = LADO_ESQUERDO
        else:
            lado = LADO_CENTRO
        if efetivo is not None:
            nivel = max(0, min(255, max(int(efetivo[0]), int(efetivo[1]))))
        return [Evento(agora, uniq, TIPO_RUMBLE, lado, nivel / 255.0)]


def anotar_o_rumble(
    daemon: Any,
    uniq: str,
    fraco: int,
    forte: int,
    agora: float | None = None,
    *,
    efetivo: tuple[int, int] | None = None,
) -> None:
    """Leva a borda do rumble ao motor ligado. Nunca levanta.

    ``fraco``/``forte`` são o pedido CRU do jogo (a borda e o lado); ``efetivo`` é o
    par depois da barra de intensidade, e dá só a energia do toque.
    """
    motor = motor_do(daemon)
    if motor is None or not motor.ligado:
        return
    try:
        instante = time.monotonic() if agora is None else agora
        for evento in motor.borda_do_rumble.ver(uniq, fraco, forte, instante, efetivo):
            motor.anotar(evento)
    except Exception:
        logger.debug("tato_vivo_borda_do_rumble_falhou", exc_info=True)


# O-TIRO-VEM-DO-LADO-CERTO-01: o estalo do som do jogo dá o lado do toque. O som é
# um fluxo só para a mesa inteira: com um controle, o estalo é dele; com mais de
# um, vai só a quem atirou naquela janela (o tiro do inimigo não tem dono).
JANELA_DO_DISPARO_S = 0.3  # do aperto ao estalo: o quadro do jogo, o buffer e o gravador


def destinos_do_som(
    controles: Sequence[Controle], dedo: BordaDoDedo, instante: float
) -> list[str]:
    """Os controles a quem o estalo do som do jogo pertence."""
    if len(controles) == 1:
        return [controles[0].uniq]
    return [c.uniq for c in controles if dedo.atirando(c.uniq, instante)]


class AtuadorDaHaptica:
    """O toque curto do tiro, no tocador do rumble do controle do evento."""

    canal = CANAL_HAPTICA

    def __init__(
        self,
        tocar: Callable[[str, float, str, int], object],
        ouvindo: Callable[[], bool] | None = None,
    ) -> None:
        self._tocar = tocar
        self._ouvindo = ouvindo or (lambda: False)

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if evento.tipo == TIPO_SOM:
            return receita.lado_do_som
        if evento.tipo != TIPO_RUMBLE or not receita.vibracao_por_tiro:
            return False
        # Um tiro, um toque: com o ouvido no som do jogo, o toque (e o lado) vem do estalo.
        return not (receita.lado_do_som and self._ouvindo())

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        self._tocar(
            evento.uniq,
            evento.energia * receita.forca_do_toque,
            evento.lado,
            receita.duracao_do_toque_ms,
        )
        # O toque acaba em silêncio por construção: não há o que devolver.
        return None

    def devolver(self, uniq: str, agora: float) -> None:
        return None


# O-SOM-DO-TIRO-SAI-TAMBEM-NO-CONTROLE-01: o estalo recortado vai ao alto-falante de quem atirou.
class AtuadorDoSom:
    """O estalo do tiro no alto-falante do controle do evento."""

    canal = CANAL_SOM

    def __init__(self, tocar: Callable[[str, Any], object]) -> None:
        self._tocar = tocar

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        return (
            evento.tipo == TIPO_SOM
            and receita.som_no_controle
            and evento.recorte is not None
        )

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        self._tocar(evento.uniq, evento.recorte)
        # O recorte acaba em silêncio por construção: não há o que devolver.
        return None

    def devolver(self, uniq: str, agora: float) -> None:
        return None


# O-GATILHO-ACOMPANHA-O-RITMO-DO-TIRO-01: o ritmo do tiro troca o bloco do gatilho.
# O jogo escreve o gatilho uma vez por arma e o firmware rearma sozinho; enquanto
# `docs/protocol/o-que-o-jogo-manda-por-tiro.md` não mostrar um jogo que rearma
# por tiro, o motor não escreve nada por tiro: só troca o bloco quando o ritmo
# muda, com os presets que a tela já tem (nenhum byte novo).
GATILHO_ARMA = "arma"
GATILHO_RAJADA = "rajada"
RITMO_DA_ARMA_S = 0.25  # tiros espaçados: o estalo de cada aperto
RITMO_DA_RAJADA_S = 0.11  # rajada; entre os dois, o modo fica (a histerese)
MESMO_TIRO_S = 0.05  # o rumble que chega junto do aperto é o mesmo tiro
CICLO_DO_GATILHO_S = 0.032  # um ciclo do laço de saída com quatro controles
VOLTA_DO_GATILHO_S = 1.5
_PRESET_DO_GATILHO = {
    GATILHO_ARMA: "SemiAutoGun",
    GATILHO_RAJADA: "MultiPositionVibration",
}
_LADO_DO_BACKEND = {LADO_ESQUERDO: "left", LADO_DIREITO: "right"}


def bloco_do_gatilho(modo: str, receita: Receita) -> bytes:
    """O bloco cru de 11 bytes do preset da tela, no layout que o relatório leva."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    nome = _PRESET_DO_GATILHO[modo]
    spec = get_spec(nome)
    valores = {p.name: p.default for p in spec.params} if spec is not None else {}
    if modo == GATILHO_RAJADA:
        valores["frequency"] = receita.frequencia_da_rajada_hz
    efeito = build_from_name(nome, valores)
    f = efeito.forces
    # O relatório leva o `forces[6]` no décimo byte do bloco (`common[19]` do backend).
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


class AtuadorDoGatilho:
    """Arma ou rajada, por lado e por controle, conforme o intervalo entre tiros."""

    canal = CANAL_GATILHO

    def __init__(
        self,
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], object],
        apertado: Callable[[str, str], bool] | None = None,
        largar: Callable[[str], object] | None = None,
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        self._ultimo_tiro: dict[tuple[str, str], float] = {}
        self._desejado: dict[tuple[str, str], str] = {}
        self._escrito: dict[tuple[str, str], str] = {}
        self._escreveu_em: dict[str, float] = {}

    def _lados(self, evento: Evento) -> list[str]:
        if evento.tipo == TIPO_DEDO:
            return [evento.lado] if evento.lado in _LADO_DO_BACKEND else []
        if evento.tipo == TIPO_RUMBLE and self.apertado is not None:
            # A arma automática: um aperto só, e o jogo pede o motor a cada bala.
            return [lado for lado in _LADO_DO_BACKEND if self.apertado(evento.uniq, lado)]
        return []

    def _ritmo(self, uniq: str, lado: str, instante: float) -> None:
        chave = (uniq, lado)
        ultimo = self._ultimo_tiro.get(chave)
        if ultimo is not None and instante - ultimo < MESMO_TIRO_S:
            return
        self._ultimo_tiro[chave] = instante
        if ultimo is None or instante - ultimo >= RITMO_DA_ARMA_S:
            modo = GATILHO_ARMA
        elif instante - ultimo <= RITMO_DA_RAJADA_S:
            modo = GATILHO_RAJADA
        else:
            modo = self._desejado.get(chave, GATILHO_ARMA)
        self._desejado[chave] = modo

    def _a_trocar(self, uniq: str) -> list[str]:
        return [
            lado
            for lado in _LADO_DO_BACKEND
            if (uniq, lado) in self._desejado
            and self._desejado[(uniq, lado)] != self._escrito.get((uniq, lado))
        ]

    def ouvir(self, eventos: list[Evento], receita: Receita) -> None:
        """O ritmo de cada lado sai do tique inteiro, antes de qualquer escrita."""
        if not receita.gatilho_no_ritmo:
            return
        for evento in eventos:
            for lado in self._lados(evento):
                self._ritmo(evento.uniq, lado, evento.instante)

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if not receita.gatilho_no_ritmo or not self._lados(evento):
            return False
        ultima = self._escreveu_em.get(evento.uniq)
        if ultima is not None and evento.instante - ultima < CICLO_DO_GATILHO_S:
            return False
        return bool(self._a_trocar(evento.uniq))

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        for lado in self._a_trocar(evento.uniq):
            modo = self._desejado[(evento.uniq, lado)]
            self._escrever(
                evento.uniq, _LADO_DO_BACKEND[lado], bloco_do_gatilho(modo, receita)
            )
            self._escrito[(evento.uniq, lado)] = modo
        self._escreveu_em[evento.uniq] = agora
        return agora + VOLTA_DO_GATILHO_S

    def prolongar(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        if not receita.gatilho_no_ritmo or not self._lados(evento):
            return None
        return agora + VOLTA_DO_GATILHO_S

    def soltar(self, uniq: str) -> None:
        """O jogo tomou o gatilho: o que o motor escreveu deixou de valer."""
        self._esquecer(uniq)
        if self._largar is not None:
            self._largar(uniq)

    def _esquecer(self, uniq: str) -> None:
        for lado in _LADO_DO_BACKEND:
            self._escrito.pop((uniq, lado), None)
        self._escreveu_em.pop(uniq, None)

    def devolver(self, uniq: str, agora: float) -> None:
        self._esquecer(uniq)
        self._devolver(uniq)


# A-LUZ-RESPIRA-A-CADA-TIRO-01: a barra pulsa (ou troca de cor) a cada tiro e volta.
# Teto de 3 subidas por segundo por controle (WCAG 2.3.1, três flashes por
# segundo), cobrado aqui e não só na tela: o tiro que chega com a luz ainda no
# pico estende o pico, e a rajada vira um brilho contínuo, nunca um pisca-pisca.
REACAO_PULSA = "pulsa"
REACAO_EVENTO = "evento"
TETO_DA_LUZ_POR_S = 3
JANELA_DA_LUZ_S = 1.0  # a janela do teto: três subidas por segundo
SEGURA_DA_LUZ_S = 0.12  # o pico; a volta vem no máximo um tique depois
GANHO_MINIMO_DO_PULSO = 1.3  # abaixo disso a cor já está no máximo e o pulso mergulha
MERGULHO_DO_PULSO = 0.35
COR_DO_EVENTO_PADRAO = (255, 255, 255)
_TIPOS_DA_LUZ = frozenset({TIPO_DEDO, TIPO_RUMBLE})


def pico_do_pulso(base: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """A cor do perfil no brilho máximo; se ela já está lá, o pulso é um mergulho."""
    maior = max(base)
    if maior <= 0:
        return None
    ganho = 255.0 / maior
    if ganho >= GANHO_MINIMO_DO_PULSO:
        r, g, b = (min(255, round(c * ganho)) for c in base)
    else:
        r, g, b = (max(1, round(c * MERGULHO_DO_PULSO)) if c else 0 for c in base)
    return (r, g, b)


class SessaoDoMotor:
    """Os canais de estado que o motor segura em cada controle.

    A volta do backend é a sessão inteira (`end_game_session_for` devolve o
    gatilho E a luz do perfil): ela só sai quando o motor solta o último canal
    daquele controle. Se o jogo tomou o canal, o motor larga sem encerrar.
    """

    def __init__(self, encerrar: Callable[[str], object]) -> None:
        self._encerrar = encerrar
        self._canais: dict[str, set[str]] = {}

    def tomar(self, uniq: str, canal: str) -> None:
        self._canais.setdefault(uniq, set()).add(canal)

    def segura(self, uniq: str) -> frozenset[str]:
        return frozenset(self._canais.get(uniq, ()))

    def _tirar(self, uniq: str, canal: str) -> bool:
        canais = self._canais.get(uniq)
        if not canais or canal not in canais:
            return False
        canais.discard(canal)
        if canais:
            return False
        del self._canais[uniq]
        return True

    def soltar(self, uniq: str, canal: str) -> bool:
        """Solta o canal; ``True`` quando era o último e a sessão voltou ao perfil."""
        if not self._tirar(uniq, canal):
            return False
        self._encerrar(uniq)
        return True

    def largar(self, uniq: str, canal: str) -> None:
        self._tirar(uniq, canal)


class AtuadorDaLuz:
    """O pulso de brilho, ou a cor do evento, na barra do controle do tiro."""

    canal = CANAL_LUZ

    def __init__(
        self,
        pintar: Callable[[str, tuple[int, int, int]], object],
        cor_de: Callable[[str], tuple[int, int, int] | None],
        devolver: Callable[[str], bool],
        largar: Callable[[str], object] | None = None,
    ) -> None:
        self._pintar = pintar
        self._cor_de = cor_de
        self._devolver = devolver
        self._largar = largar
        self._base: dict[str, tuple[int, int, int]] = {}
        self._no_pico: set[str] = set()
        self._subidas: dict[str, deque[float]] = {}

    @staticmethod
    def _quer(evento: Evento, receita: Receita) -> bool:
        return (
            receita.reacao_ao_tiro in (REACAO_PULSA, REACAO_EVENTO)
            and evento.tipo in _TIPOS_DA_LUZ
        )

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if not self._quer(evento, receita) or evento.uniq in self._no_pico:
            return False
        subidas = self._subidas.setdefault(evento.uniq, deque())
        while subidas and evento.instante - subidas[0] >= JANELA_DA_LUZ_S:
            subidas.popleft()
        if len(subidas) >= TETO_DA_LUZ_POR_S:
            return False
        # Fora do pico não há pulso no ar: a cor se lê de novo a cada tiro. O tiro
        # que o jogo ou o teto recusam não pode deixar guardada a cor de antes
        # da troca de perfil, que o pulso seguinte pintaria.
        base = self._cor_de(evento.uniq)
        if base is None or max(base) <= 0:
            self._base.pop(evento.uniq, None)
            return False  # a barra apagada não tem o que respirar
        self._base[evento.uniq] = base
        return True

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        uniq = evento.uniq
        base = self._base[uniq]
        if receita.reacao_ao_tiro == REACAO_PULSA:
            cor = pico_do_pulso(base) or base
        else:
            cor = receita.cor_do_evento or COR_DO_EVENTO_PADRAO
        self._pintar(uniq, cor)
        self._no_pico.add(uniq)
        self._subidas.setdefault(uniq, deque()).append(evento.instante)
        return agora + SEGURA_DA_LUZ_S

    def prolongar(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        if evento.uniq not in self._no_pico or not self._quer(evento, receita):
            return None
        return agora + SEGURA_DA_LUZ_S

    def soltar(self, uniq: str) -> None:
        """O jogo tomou a barra: a cor agora é dele."""
        self._base.pop(uniq, None)
        self._no_pico.discard(uniq)
        if self._largar is not None:
            self._largar(uniq)

    def devolver(self, uniq: str, agora: float) -> None:
        base = self._base.pop(uniq, None)
        self._no_pico.discard(uniq)
        if not self._devolver(uniq) and base is not None:
            # O motor ainda segura outro canal deste controle: a cor volta à mão,
            # e a luz repintada não prende a sessão (ela sai com o outro canal).
            self._pintar(uniq, base)
            if self._largar is not None:
                self._largar(uniq)


# --- A ligação com o daemon ----------------------------------------------


@dataclass(frozen=True)
class Controle:
    """Um controle da mesa como o motor o vê: identidade, pad e os gatilhos."""

    uniq: str
    vpad: Any
    l2: int = 0
    r2: int = 0


def _inteiro(valor: Any) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def controles_do_daemon(daemon: Any) -> list[Controle]:
    """P1 (o pad primário) e P2 a P4 (os jogadores do co-op), cada um com o seu."""
    vistos: dict[str, Controle] = {}
    controller = getattr(daemon, "controller", None)
    primario = getattr(controller, "primary_uniq", None)
    if isinstance(primario, str) and primario:
        estado = getattr(daemon, "_last_state", None)
        vistos[primario] = Controle(
            primario,
            getattr(daemon, "_gamepad_device", None),
            _inteiro(getattr(estado, "l2_raw", 0)),
            _inteiro(getattr(estado, "r2_raw", 0)),
        )
    coop = getattr(daemon, "_coop_manager", None)
    jogadores = getattr(coop, "_players", None)
    if isinstance(jogadores, dict):
        for mac, jogador in list(jogadores.items()):
            if not isinstance(mac, str) or mac in vistos:
                continue
            l2 = r2 = 0
            leitor = getattr(jogador, "reader", None)
            with contextlib.suppress(Exception):
                foto = leitor.snapshot() if leitor is not None else None
                l2 = _inteiro(getattr(foto, "l2_raw", 0))
                r2 = _inteiro(getattr(foto, "r2_raw", 0))
            vistos[mac] = Controle(mac, getattr(jogador, "vpad", None), l2, r2)
    return list(vistos.values())


def ha_jogo(daemon: Any) -> bool:
    """O sinal de jogo do daemon: a autoridade sticky, ou uma janela de jogo em foco."""
    if getattr(daemon, "display_authority", "unknown") == "game":
        return True
    olhar = getattr(daemon, "_janela_de_jogo_em_foco", None)
    if callable(olhar):
        with contextlib.suppress(Exception):
            return bool(olhar())
    return False


def estado_do_controle(
    controle: Controle, jogo: bool, sessao_ha_s: float | None = None
) -> EstadoDoCanal:
    vpad = controle.vpad
    visto: Mapping[str, float] = {}
    with contextlib.suppress(Exception):
        cru = getattr(vpad, "visto_ha_s", None)
        if isinstance(cru, Mapping):
            visto = cru
    return EstadoDoCanal(
        modo=modo_do_pad(vpad),
        visto_ha_s=visto,
        sessao_aberta=bool(getattr(vpad, "game_open", False)),
        ha_jogo=jogo,
        sessao_ha_s=sessao_ha_s,
    )


#: O nome que não achou arquivo com o slug dele e a receita que o `load_profile`
#: trouxe: o laço só volta a varrer quando o `active_profile` muda.
_PELO_CARREGADOR: tuple[str, Receita] | None = None


def receita_ativa(daemon: Any) -> Receita:
    """A receita do perfil ativo, lida da vista (o computador por baixo do jogo).

    Sem perfil, ou sem receita, desligada. Lê pelo `perfil_em_disco`, que só lê o
    arquivo (sem semear, sem varrer), como o ganho da háptica: este é o laço de
    60 Hz do daemon, e o `load_profile` semeia e reaponta perfis de jogo. Quando o
    nome não tem arquivo com o slug dele, cai no `load_profile` UMA vez por nome
    (A-RECEITA-DO-TATO-SE-LE-SEM-SEMEAR-NEM-VARRER-01).
    """
    global _PELO_CARREGADOR
    nome = getattr(getattr(daemon, "store", None), "active_profile", None)
    if not isinstance(nome, str) or not nome:
        return DESLIGADA
    try:
        from hefesto_dualsense4unix.profiles.loader import perfil_em_disco
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        perfil = perfil_em_disco(nome)
        if perfil is not None:
            _PELO_CARREGADOR = None
            return receita_do_perfil(o_que_vale(perfil))
        if _PELO_CARREGADOR is not None and _PELO_CARREGADOR[0] == nome:
            return _PELO_CARREGADOR[1]
        _PELO_CARREGADOR = (nome, DESLIGADA)
        from hefesto_dualsense4unix.profiles.loader import load_profile

        receita = receita_do_perfil(o_que_vale(load_profile(nome)))
        _PELO_CARREGADOR = (nome, receita)
        return receita
    except Exception:
        logger.debug("tato_vivo_perfil_ilegivel", exc_info=True)
        return DESLIGADA


def atuadores_de_producao(daemon: Any) -> list[Atuador]:
    """Os canais que o motor sabe escrever hoje."""

    def ouvindo() -> bool:
        motor = motor_do(daemon)
        return bool(motor is not None and getattr(motor.ouvido, "ouvindo", False))

    def tocar(uniq: str, energia: float, lado: str, duracao_ms: int) -> object:
        alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
        tocar_o_toque = getattr(alto_falante, "tocar_o_toque", None)
        if not callable(tocar_o_toque):
            return False
        return tocar_o_toque(uniq, energia, lado, duracao_ms)

    def estalo(uniq: str, recorte: Any) -> object:
        alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
        tocar_o_estalo = getattr(alto_falante, "tocar_o_estalo", None)
        if not callable(tocar_o_estalo):
            return False
        return tocar_o_estalo(uniq, recorte)

    controller = getattr(daemon, "controller", None)

    def encerrar(uniq: str) -> object:
        devolver = getattr(controller, "end_game_session_for", None)
        return devolver(uniq) if callable(devolver) else False

    sessao = SessaoDoMotor(encerrar)

    def gatilho(uniq: str, lado: str, bloco: bytes) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_GATILHO)
        return escrever(uniq, lado, bloco)

    def apertado(uniq: str, lado: str) -> bool:
        motor = motor_do(daemon)
        return motor is not None and motor.borda_do_dedo.apertado(uniq, lado)

    def pintar(uniq: str, cor: tuple[int, int, int]) -> object:
        escrever = getattr(controller, "set_game_output_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_LUZ)
        return escrever(uniq, led=cor)

    def cor_de(uniq: str) -> tuple[int, int, int] | None:
        ler = getattr(controller, "resolved_led_for", None)
        cor = ler(uniq) if callable(ler) else None
        if not isinstance(cor, tuple) or len(cor) != 3:
            return None
        return (int(cor[0]), int(cor[1]), int(cor[2]))

    return [
        AtuadorDaHaptica(tocar, ouvindo),
        AtuadorDoSom(estalo),
        AtuadorDoGatilho(
            gatilho,
            lambda uniq: sessao.soltar(uniq, CANAL_GATILHO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_GATILHO),
        ),
        AtuadorDaLuz(
            pintar,
            cor_de,
            lambda uniq: sessao.soltar(uniq, CANAL_LUZ),
            lambda uniq: sessao.largar(uniq, CANAL_LUZ),
        ),
    ]


def motor_do(daemon: Any) -> TatoVivo | None:
    motor = getattr(daemon, "_tato_vivo", None)
    return motor if isinstance(motor, TatoVivo) else None


class Passo:
    """Um tique do laço de produção, separado para se testar com relógio injetado."""

    def __init__(self, daemon: Any, motor: TatoVivo) -> None:
        self.daemon = daemon
        self.motor = motor
        self.dedo = motor.borda_do_dedo
        self.receita_vigente: Receita = DESLIGADA
        self.jogo = False
        self._lida_em = float("-inf")
        # Quando o pad de cada controle abriu a sessão de agora (None: já estava aberta).
        self._aberta_em: dict[str, float | None] = {}

    def receita_de_agora(self, agora: float) -> Receita:
        if agora - self._lida_em >= RELEITURA_DA_RECEITA_S:
            self._lida_em = agora
            self.receita_vigente = receita_ativa(self.daemon)
        return self.receita_vigente

    def __call__(self, agora: float) -> int:
        receita = self.receita_de_agora(agora)
        ligado = receita.ligada
        if not ligado:
            if self.motor.ligado:
                self.motor.parar(agora)
            self.motor.ligado = False
            self._aberta_em.clear()
            return 0
        self.motor.ligado = True
        controles = controles_do_daemon(self.daemon)
        for controle in controles:
            for evento in self.dedo.ver(controle.uniq, controle.l2, controle.r2, agora):
                self.motor.anotar(evento)
        self._ouvir_o_jogo(receita, controles)
        jogo = self.jogo = ha_jogo(self.daemon)
        por_uniq = {
            c.uniq: estado_do_controle(c, jogo, self._sessao_ha_s(c, agora)) for c in controles
        }
        return self.motor.tique(agora, por_uniq.get, receita)

    def tique_do_laco(self, agora: float) -> int:
        """O tique do laço de 60 Hz: o que falha num tique fica no log, e o seguinte vem."""
        try:
            return self(agora)
        except Exception:
            logger.debug("tato_vivo_tique_falhou", exc_info=True)
            return 0

    def _sessao_ha_s(self, controle: Controle, agora: float) -> float | None:
        """A idade da sessão aberta, vista abrir por este passo; ``None`` se não se viu."""
        aberta = bool(getattr(controle.vpad, "game_open", False))
        if not aberta:
            self._aberta_em[controle.uniq] = agora
            return None
        if controle.uniq not in self._aberta_em:
            self._aberta_em[controle.uniq] = None
        desde = self._aberta_em[controle.uniq]
        return None if desde is None else max(0.0, agora - desde)

    def _ouvir_o_jogo(self, receita: Receita, controles: Sequence[Controle]) -> None:
        """Sobe o ouvido quando a receita pede o som, e leva cada estalo a quem atirou."""
        ouvido = self.motor.ouvido
        if ouvido is None:
            return
        if receita.lado_do_som or receita.som_no_controle:
            ouvido.comecar()
        for estalo in ouvido.tirar():
            for uniq in destinos_do_som(controles, self.dedo, estalo.instante):
                self.motor.anotar(
                    Evento(estalo.instante, uniq, TIPO_SOM, estalo.lado, estalo.energia,
                           getattr(estalo, "recorte", None))
                )


async def tato_vivo_loop(daemon: DaemonProtocol, motor: TatoVivo) -> None:
    passo = Passo(daemon, motor)
    if motor.ouvido is None:
        from hefesto_dualsense4unix.integrations.transiente_do_jogo import OuvidoDoJogo

        motor.ouvido = OuvidoDoJogo(
            lambda: (
                motor.ligado
                and (passo.receita_vigente.lado_do_som or passo.receita_vigente.som_no_controle)
                and passo.jogo
            ),
            recortar=lambda: passo.receita_vigente.som_no_controle,
        )
    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_S)
            passo.tique_do_laco(time.monotonic())
    finally:
        motor.parar()
        with contextlib.suppress(Exception):
            await asyncio.to_thread(motor.ouvido.parar)


def start_tato_vivo(daemon: DaemonProtocol) -> None:
    """Sobe o motor do tato vivo. Desligado pela receita, o laço só lê o perfil."""
    motor = TatoVivo(atuadores_de_producao(daemon))
    daemon._tato_vivo = motor  # type: ignore[attr-defined]
    task = asyncio.create_task(tato_vivo_loop(daemon, motor), name="tato_vivo_loop")
    daemon._tasks.append(task)
    logger.info("tato_vivo_iniciado")


__all__ = [
    "CAMPOS_DA_RECEITA",
    "CAMPO_DA_RECEITA",
    "CANAIS",
    "DESLIGADA",
    "MODO_DUALSENSE",
    "MODO_NATIVO",
    "MODO_XBOX",
    "Atuador",
    "AtuadorDaHaptica",
    "AtuadorDaLuz",
    "AtuadorDoGatilho",
    "AtuadorDoSom",
    "BordaDoDedo",
    "BordaDoRumble",
    "Controle",
    "EstadoDoCanal",
    "Evento",
    "Passo",
    "Receita",
    "SessaoDoMotor",
    "TatoVivo",
    "Teto",
    "anotar_o_rumble",
    "bloco_do_gatilho",
    "controles_do_daemon",
    "decidir",
    "destinos_do_som",
    "modo_do_pad",
    "motor_do",
    "pico_do_pulso",
    "receita_do_estilo",
    "receita_do_perfil",
    "start_tato_vivo",
]
