"""O tato vivo: reage ao tiro e toca os momentos da imersão, só onde o jogo cala.

Toda escrita passa por ``decidir`` (o jogo manda; Modo Nativo calado), pelo teto de 12
pulsos por segundo por controle e 40 no total, e tem prazo: o tique devolve o canal, ou
solta sem devolver se o jogo passou a mandar. Escreve só pelas APIs por ``uniq`` (P1 a P4,
cabo e rádio). Nasce desligado e liga pela receita do perfil ativo (:func:`receita_do_estilo`
ou :func:`planos_do_perfil`), com o desvio ``receita_do_tato`` por cima. A história:
O-TATO-VIVO-SO-FALA-ONDE-O-JOGO-CALA-01 (08/10/2026).
"""
from __future__ import annotations

import asyncio
import contextlib
import math
import threading
import time
from array import array
from collections import deque
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, cast

from hefesto_dualsense4unix.core.events import EventTopic, tem_assinante
from hefesto_dualsense4unix.core.physical_report_reader import TRIGGER_ESTADO_DISPAROU
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.caderno_do_tique import a_resposta_chegou, no_caderno
from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO
from hefesto_dualsense4unix.daemon.lifecycle import (
    MODO_DUALSENSE,
    MODO_NATIVO,
    MODO_XBOX,
    modo_do_controle,
    modo_do_pad,
    o_hefesto_fala_no_modo,
)
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao
from hefesto_dualsense4unix.daemon.subsystems.diario_do_corpo import (
    PASSO_DO_DIARIO_S,
    RECUSA_ECONOMIA,
    RECUSA_FORCA_ZERO,
    RECUSA_JOGO_NO_ENDPOINT,
    RECUSA_SEM_APARELHO,
    DiarioDoCorpo,
)
from hefesto_dualsense4unix.daemon.subsystems.intensidade_da_cena import IntensidadeDaCena
from hefesto_dualsense4unix.integrations.classe_do_rumble import calado
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    QUEDA_NO_MOTOR,
    QUEDA_PASSOU_DO_PRAZO,
)
from hefesto_dualsense4unix.profiles import formas_de_haptica
from hefesto_dualsense4unix.profiles.efeitos_de_imersao import (
    FAMILIAS,
    QUANDO_PASSOU_DO_CLIQUE,
    QUANDO_PRONTO,
    Imersao,
    Momento,
    ajustes_da_imersao,
    imersao_dos_numeros,
    momentos_no_modo,
)
from hefesto_dualsense4unix.profiles.efeitos_de_imersao import (
    POR_CHAVE as POR_CHAVE_DE_IMERSAO,
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
CANAL_MOTORES = "motores"

CANAIS_DE_ESTADO = frozenset({CANAL_GATILHO, CANAL_LUZ})

_CARIMBO_DO_CANAL: dict[str, str] = {
    CANAL_GATILHO: "trigger",
    CANAL_LUZ: "lightbar",
    CANAL_HAPTICA: "audio_do_jogo",
    CANAL_SOM: "audio_do_jogo",
    CANAL_MOTORES: "rumble",
}


JANELA_DO_JOGO_S = 3.0
TETO_POR_CONTROLE = 12
TETO_TOTAL = 40
JANELA_DO_TETO_S = 1.0
INTERVALO_S = 1.0 / 60.0
RELEITURA_DA_RECEITA_S = 1.0
PORTA_DO_TATO = "receita do tato"
CORPO_MAX_PEDACOS = 16
SINAL_DO_CORPO = 0.001
ESCRITAS_DA_QUEDA_POR_S = 1000.0 / 60
SILENCIO_DA_QUEDA_S = 0.25
PRAZO_DA_PONTE_S = 15.0
RECUSAS_SEM_QUEDA = frozenset({RECUSA_FORCA_ZERO, RECUSA_JOGO_NO_ENDPOINT})

CAMPO_DA_RECEITA = "receita_do_tato"

TIPO_DEDO = "dedo"
TIPO_RUMBLE = "rumble_tiro"
TIPO_SOM = "som_tiro"
TIPO_SOLTA = "solta_tiro"
TIPO_BATIDA = "batida_do_som"

LADO_ESQUERDO = "esquerdo"
LADO_DIREITO = "direito"
LADO_CENTRO = "centro"

REACOES_DA_LUZ = ("parada", "pulsa", "evento", "batida")


@dataclass(frozen=True)
class EstadoDoCanal:
    """O que a política precisa saber de UM controle, num instante."""

    modo: str
    visto_ha_s: Mapping[str, float] = field(default_factory=dict)
    sessao_aberta: bool = False
    ha_jogo: bool = False
    sessao_ha_s: float | None = None
    motores_no_audio: bool = False


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
    """``True`` quando o jogo cala neste canal e o motor pode escrever.

    Os motores no áudio somam ao que o jogo toca: ali o jogo não cala nada, e só o Nativo cala.
    """
    if canal == CANAL_MOTORES and estado.motores_no_audio:
        return estado.ha_jogo and estado.modo != MODO_NATIVO
    if _o_modo_cala_o_motor(estado):
        return False
    carimbo = _CARIMBO_DO_CANAL.get(canal)
    if carimbo is None:
        return False
    idade = estado.visto_ha_s.get(carimbo)
    if idade is not None and idade < JANELA_DO_JOGO_S:
        return False
    if canal in CANAIS_DE_ESTADO and estado.sessao_aberta:
        if _da_sessao(idade, estado):
            return False
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
    recorte: Any = field(default=None, compare=False)
    duracao_s: float = 0.0


def _limitar(valor: Any, baixo: float, alto: float, padrao: float) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return padrao
    if numero != numero:
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
    momentos_da_imersao: bool = False
    efeitos_escolhidos: bool = False
    som_no_corpo_escolhido: bool = False
    grao_escolhido: bool = False
    motor_de_epoca_escolhido: bool = False
    padroes_escolhidos: bool = False
    pancada_escolhida: bool = False
    som_quando_o_jogo_cala: bool = False
    rumble_no_dedo: bool = False

    @property
    def ligada(self) -> bool:
        return (
            self.vibracao_por_tiro
            or self.gatilho_no_ritmo
            or self.reacao_ao_tiro != "parada"
            or self.lado_do_som
            or self.som_no_controle
            or self.momentos_da_imersao
            or self.efeitos_escolhidos
            or self.som_no_corpo_escolhido
            or self.grao_escolhido
            or self.motor_de_epoca_escolhido
            or self.padroes_escolhidos
            or self.som_quando_o_jogo_cala
            or self.rumble_no_dedo
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
            momentos_da_imersao=bool(campo("momentos_da_imersao", False)),
            efeitos_escolhidos=bool(campo("efeitos_escolhidos", False)),
            som_no_corpo_escolhido=bool(campo("som_no_corpo_escolhido", False)),
            grao_escolhido=bool(campo("grao_escolhido", False)),
            motor_de_epoca_escolhido=bool(campo("motor_de_epoca_escolhido", False)),
            padroes_escolhidos=bool(campo("padroes_escolhidos", False)),
            pancada_escolhida=bool(campo("pancada_escolhida", False)),
            som_quando_o_jogo_cala=bool(campo("som_quando_o_jogo_cala", False)),
            rumble_no_dedo=bool(campo("rumble_no_dedo", False)),
        )


DESLIGADA = Receita()

CAMPOS_DA_RECEITA: tuple[str, ...] = tuple(f.name for f in fields(Receita))

FORCA_DO_DEGRAU: dict[str, float] = {"max": 1.0, "balanceado": 0.6, "economia": 0.35}
REACAO_DA_LUZ_DO_ESTILO: dict[str, str] = {
    "parada": "parada",
    "respira": "pulsa",
    "pisca": "pulsa",
    "batida": "batida",
}
TOQUE_DE_SEMPRE_MS = 40
TOQUE_MINIMO_MS = 25
TOQUE_MAXIMO_MS = 60
ESTILOS_DE_RAJADA = frozenset({"fps", "acao", "terror"})  # (noqa-acento)
SOM_NO_CONTROLE_DO_ESTILO = False


def duracao_do_toque_do_estilo(duracao_da_vibracao_ms: int) -> int:
    """Os ms do toque para a duração da vibração do estilo: ``40 * d / 200``, de 25 a 60."""
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import DURACAO_DE_SEMPRE_MS

    toque = round(TOQUE_DE_SEMPRE_MS * duracao_da_vibracao_ms / DURACAO_DE_SEMPRE_MS)
    return max(TOQUE_MINIMO_MS, min(TOQUE_MAXIMO_MS, toque))


def receita_do_estilo(estilo: Any) -> Receita:
    """A receita do motor para um ``Estilo`` de ``estilos_de_jogo``: a tradução."""
    invisivel = getattr(estilo, "receita_invisivel", None)
    if invisivel is None:
        return DESLIGADA
    padrao = padroes_de_vibracao.POR_ESTILO.get(estilo.chave)
    return Receita(
        vibracao_por_tiro=bool(invisivel.toque_por_tiro),
        forca_do_toque=FORCA_DO_DEGRAU.get(estilo.vibracao, DESLIGADA.forca_do_toque),
        duracao_do_toque_ms=duracao_do_toque_do_estilo(int(invisivel.duracao_da_vibracao_ms)),
        gatilho_no_ritmo=estilo.chave in ESTILOS_DE_RAJADA,
        reacao_ao_tiro=REACAO_DA_LUZ_DO_ESTILO.get(invisivel.luz, DESLIGADA.reacao_ao_tiro),
        lado_do_som=bool(invisivel.lado_do_som),
        som_no_controle=SOM_NO_CONTROLE_DO_ESTILO,
        som_no_corpo_escolhido=(
            formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.SOM_NO_CORPO),
        grao_escolhido=formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.GRAO,
        motor_de_epoca_escolhido=(
            formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.MOTOR_DE_EPOCA),
        padroes_escolhidos=padrao is not None,
        pancada_escolhida=padrao == "pancada_do_lado",
        som_quando_o_jogo_cala=bool(getattr(invisivel, "som_quando_o_jogo_cala", False)),
        rumble_no_dedo=bool(getattr(invisivel, "rumble_no_dedo", False)),
    )


def _ler(alvo: Any, nome: str) -> Any:
    """Um campo do perfil, seja ele o modelo ou o JSON cru."""
    if isinstance(alvo, Mapping):
        return alvo.get(nome)
    return getattr(alvo, nome, None)


def _escolhas_do_campo(
    perfil: Any, campo: str, valida: Callable[[object], str | None]
) -> dict[str, str]:
    controles = _ler(perfil, "controllers") if perfil is not None else None
    fora: dict[str, str] = {}
    for chave, dele in (controles.items() if isinstance(controles, Mapping) else ()):
        alvo = norm_mac(str(chave))
        escolha = valida(_ler(_ler(dele, "rumble"), campo))
        if alvo and escolha is not None:
            fora[alvo] = escolha
    return fora


def escolhas_do_perfil(perfil: Any) -> dict[str, str]:
    """A forma do toque que cada controle escolheu (``rumble.efeito_haptico``), por ``norm_mac``.

    Só entra quem escolheu, «—» e «Do estilo» inclusive; escolha que não se lê também fica fora.
    O controle fora daqui vale o que ``formas_de_haptica.escolha_que_vale`` diz pelo estilo.
    """
    return _escolhas_do_campo(perfil, "efeito_haptico", formas_de_haptica.escolha_valida)


def padroes_do_perfil(perfil: Any) -> dict[str, str]:
    """O padrão que cada controle escolheu para os motores (``rumble.efeito_imersao``)."""
    return _escolhas_do_campo(perfil, "efeito_imersao", padroes_de_vibracao.escolha_valida)


def receita_do_perfil(perfil: Any) -> Receita:
    """A receita do estilo que o perfil guarda, com o desvio dele por cima."""
    if perfil is None:
        return DESLIGADA

    base = DESLIGADA
    chave = _ler(perfil, "estilo")
    if isinstance(chave, str):
        from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

        estilo = POR_CHAVE.get(chave)
        if estilo is not None:
            base = receita_do_estilo(estilo)
    if planos_do_perfil(perfil):
        base = replace(base, momentos_da_imersao=True)
    escolhas = escolhas_do_perfil(perfil)
    if escolhas:
        base = replace(
            base,
            efeitos_escolhidos=base.efeitos_escolhidos or any(
                v in formas_de_haptica.FORMAS for v in escolhas.values()),
            som_no_corpo_escolhido=(
                base.som_no_corpo_escolhido
                or formas_de_haptica.SOM_NO_CORPO in escolhas.values()),
            grao_escolhido=base.grao_escolhido or formas_de_haptica.GRAO in escolhas.values(),
            motor_de_epoca_escolhido=(
                base.motor_de_epoca_escolhido
                or formas_de_haptica.MOTOR_DE_EPOCA in escolhas.values()),
        )
    padroes = padroes_do_perfil(perfil)
    if padroes:
        base = replace(
            base,
            padroes_escolhidos=base.padroes_escolhidos or any(
                v not in (padroes_de_vibracao.SEM_EFEITO, padroes_de_vibracao.DO_ESTILO)
                for v in padroes.values()),
            pancada_escolhida=base.pancada_escolhida or "pancada_do_lado" in padroes.values(),
        )
    desvio = _ler(perfil, CAMPO_DA_RECEITA)
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
        self.de_fora = FonteDeFora(self.teto)
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
        self.ouvido: Any = None
        self.momentos: MapaDosMomentos = SEM_MOMENTOS
        self.escolhas: dict[str, str] = {}
        self.escolhas_de_imersao: dict[str, str] = {}
        self.vibra_o_gatilho: VibracaoDoGatilho = SEM_VIBRACAO
        self.armas_do_gatilho: ArmasDoGatilho = SEM_ARMAS
        self.steam_input: frozenset[int] = frozenset()
        self.rumble_visto_em: dict[str, float] = {}
        self.rumble_com_forca_em: dict[str, float] = {}
        self.rumble_de_agora: dict[str, tuple[int, int]] = {}
        self.par_com_forca: dict[str, tuple[int, int]] = {}
        self.acordados_pelo_som: frozenset[str] = frozenset()
        self.disparo: dict[tuple[str, str], int] = {}
        self.volta: Any = None
        self.meus_toques: Any = None
        self.queda: Any = None
        self.cena = IntensidadeDaCena()

    def anotar(self, evento: Evento) -> None:
        """Põe um evento na fila. Chamável de qualquer thread."""
        with self._lock:
            self._fila.append(evento)
            self.contadores["eventos"] += 1

    def segurando(self, canal: str) -> frozenset[str]:
        """Os controles em que ``canal`` ainda espera a volta ao perfil (o pulso no ar)."""
        seguros = frozenset(uniq for uniq, dele in self._pendentes if dele == canal)
        if canal == CANAL_LUZ and self.volta is not None:
            da_volta: frozenset[str] = self.volta.segurando_a_barra()
            return seguros | da_volta
        return seguros

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
        uniqs: Iterable[str] = (),
    ) -> int:
        """Devolve o que venceu, decide cada evento da fila e escreve. Retorna as escritas.

        ``uniqs`` são os controles da mesa: o atuador que anda com o relógio (os momentos
        da imersão) olha cada um deles a cada tique, com ou sem evento. O modo que cala no meio
        do padrão devolve os motores: ali não há jogo para mandar o zero dele.
        """
        with self._lock:
            eventos = list(self._fila)
            self._fila.clear()
        self.cena.contar(eventos)
        for atuador in self.atuadores:
            ouvir = getattr(atuador, "ouvir", None)
            if callable(ouvir):
                ouvir(eventos, receita)
        for (uniq, canal), prazo in list(self._pendentes.items()):
            estado = estado_de(uniq)
            if estado is not None and not decidir(canal, estado):
                if canal == CANAL_MOTORES and _o_modo_cala_o_motor(estado):
                    self._devolver(uniq, canal, agora)
                    continue
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
        mesa = tuple(uniqs)
        for atuador in self.atuadores:
            relogio = getattr(atuador, "relogio", None)
            if not callable(relogio):
                continue
            try:
                escritas += int(relogio(self, agora, mesa, estado_de, receita))
            except Exception:
                logger.debug("tato_vivo_relogio_falhou", canal=atuador.canal, exc_info=True)
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
        if self.queda is not None:
            self.queda.soltar_tudo()
        for uniq, canal in list(self._pendentes):
            self._devolver(uniq, canal, instante)
        for atuador in self.atuadores:
            devolver_tudo = getattr(atuador, "devolver_tudo", None)
            if callable(devolver_tudo):
                try:
                    devolver_tudo(instante)
                except Exception:
                    logger.debug("tato_vivo_devolucao_falhou", canal=atuador.canal,
                                 exc_info=True)

    @property
    def pendentes(self) -> dict[tuple[str, str], float]:
        return dict(self._pendentes)

    def estado(self) -> dict[str, Any]:
        """Diagnóstico: contadores e se o motor está ligado. Nunca texto de tela."""
        return {
            "ligado": self.ligado,
            "pendentes": len(self._pendentes),
            **self.contadores,
            "intensidade_da_cena": self.cena.estado(),
        }


DEDO_DISPARA = 160
DEDO_SOLTA = 96


class BordaDoDedo:
    """O dedo que aperta o gatilho: um evento por aperto, com histerese."""

    def __init__(self, dispara: int = DEDO_DISPARA, solta: int = DEDO_SOLTA) -> None:
        self.dispara = dispara
        self.solta = solta
        self._apertado: dict[tuple[str, str], bool] = {}
        self._apertou_em: dict[str, float] = {}
        self._pico: dict[tuple[str, str], int] = {}
        self._inicio: dict[tuple[str, str], float] = {}
        self._soltas: list[Evento] = []

    def ver(self, uniq: str, l2: int, r2: int, agora: float) -> list[Evento]:
        eventos: list[Evento] = []
        for lado, valor in ((LADO_ESQUERDO, l2), (LADO_DIREITO, r2)):
            chave = (uniq, lado)
            apertado = self._apertado.get(chave, False)
            if not apertado and valor >= self.dispara:
                self._apertado[chave] = True
                self._apertou_em[uniq] = agora
                self._pico[chave] = valor
                self._inicio[chave] = agora
                eventos.append(
                    Evento(agora, uniq, TIPO_DEDO, lado, min(1.0, valor / 255.0))
                )
            elif apertado and valor <= self.solta:
                self._apertado[chave] = False
                pico = self._pico.pop(chave, valor)
                segurou = max(0.0, agora - self._inicio.pop(chave, agora))
                self._soltas.append(
                    Evento(agora, uniq, TIPO_SOLTA, lado, min(1.0, pico / 255.0), None, segurou))
            elif apertado:
                self._pico[chave] = max(self._pico.get(chave, valor), valor)
        return eventos

    def tirar_as_soltas(self) -> list[Evento]:
        """As largadas do gatilho desde a última vez (o recuo: o Coice toca aqui)."""
        soltas, self._soltas = self._soltas, []
        return soltas

    def apertado(self, uniq: str, lado: str) -> bool:
        return self._apertado.get((uniq, lado), False)

    def atirando(self, uniq: str, instante: float) -> bool:
        """O dedo deste controle segura um gatilho, ou apertou há pouco."""
        if any(self.apertado(uniq, lado) for lado in (LADO_ESQUERDO, LADO_DIREITO)):
            return True
        apertou = self._apertou_em.get(uniq)
        return apertou is not None and -MESMO_TIRO_S <= instante - apertou <= JANELA_DO_DISPARO_S


RUMBLE_DISPARA = 80
RUMBLE_SUBIDA = 64
RUMBLE_REARMA = 48
RUMBLE_JUNTA_S = 0.03


class BordaDoRumble:
    """O par ``(fraco, forte)`` do jogo, controle a controle: um evento por subida.

    A borda e o lado vêm do pedido CRU do jogo; a barra de intensidade do estilo só
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
        chave = norm_mac(uniq) or uniq
        motor.rumble_visto_em = {**motor.rumble_visto_em, chave: instante}
        motor.rumble_de_agora = {**motor.rumble_de_agora, chave: (int(fraco), int(forte))}
        if not calado(fraco, forte):
            motor.rumble_com_forca_em = {**motor.rumble_com_forca_em, chave: instante}
            motor.par_com_forca = {**motor.par_com_forca, chave: (int(fraco), int(forte))}
        for evento in motor.borda_do_rumble.ver(uniq, fraco, forte, instante, efetivo):
            motor.anotar(evento)
    except Exception:
        logger.debug("tato_vivo_borda_do_rumble_falhou", exc_info=True)


JANELA_DO_DISPARO_S = 0.3


def pede_o_ouvido(receita: Receita) -> bool:
    """A receita precisa do som do jogo: o lado, o estalo, o corpo, a pancada ou a batida."""
    return bool(
        receita.lado_do_som or receita.som_no_controle or receita.som_no_corpo_escolhido
        or receita.pancada_escolhida or receita.reacao_ao_tiro == REACAO_BATIDA
        or receita.som_quando_o_jogo_cala)


def destinos_do_som(
    controles: Sequence[Controle], dedo: BordaDoDedo, instante: float
) -> list[str]:
    """Os controles a quem o estalo do som do jogo pertence."""
    if len(controles) == 1:
        return [controles[0].uniq]
    return [c.uniq for c in controles if dedo.atirando(c.uniq, instante)]


SEM_RUMBLE_S = 20.0
ENTRADA_VIVA_S = 5.0
PASSO_DA_ENTRADA = 16
ESTILOS_DE_GOLPE = frozenset({
    "acao", "luta", "souls", "terror", "aventura", "esportes",  # (noqa-acento)
})
ESTILOS_DO_CORPO_DISCRETO = ESTILOS_DE_GOLPE - formas_de_haptica.SEM_CORPO
FORCA_DO_CORPO_DISCRETO = 0.5


def _assinatura_da_mao(entrada: Any) -> tuple[Any, ...]:
    """O que a mão faz: os botões e os eixos crus (analógicos e gatilhos)."""
    eixos = tuple(int(getattr(entrada, nome, 0)) for nome in ("lx", "ly", "rx", "ry", "l2", "r2"))
    return (frozenset(getattr(entrada, "botoes", ()) or ()), *eixos)


def _a_mao_mexeu(antes: tuple[Any, ...], agora: tuple[Any, ...]) -> bool:
    if antes[0] != agora[0]:
        return True
    return any(abs(a - b) >= PASSO_DA_ENTRADA for a, b in zip(antes[1:], agora[1:], strict=True))


class FonteDoSom:
    """Onde o som do jogo vira háptica: o controle em que o jogo não vibra há ``SEM_RUMBLE_S``,
    com a pessoa jogando. O primeiro rumble com força a faz ceder no mesmo tique."""

    def __init__(self) -> None:
        self._calado_desde: dict[str, float] = {}
        self._contagem: dict[str, int] = {}
        self._mao: dict[str, tuple[Any, ...]] = {}
        self._mexeu_em: dict[str, float] = {}

    def esquecer(self, uniq: str) -> None:
        for mapa in (self._calado_desde, self._contagem, self._mao, self._mexeu_em):
            mapa.pop(uniq, None)

    def _vibrou(self, uniq: str, vpad: Any) -> bool:
        """O pad conta um rumble com força desde o tique anterior, ou vibra agora."""
        contagem = getattr(vpad, "ff_nao_nulo_count", None)
        antes = self._contagem.get(uniq)
        if isinstance(contagem, int):
            self._contagem[uniq] = contagem
        subiu = isinstance(contagem, int) and antes is not None and contagem > antes
        par = getattr(vpad, "ff_last_sent", None)
        agora_vibra = (isinstance(par, tuple) and len(par) == 2
                       and all(isinstance(x, int) for x in par) and not calado(*par))
        return subiu or agora_vibra

    def ver(
        self, uniq: str, agora: float, *, jogo: bool, vpad: Any = None,
        rumble_em: float | None = None, entrada: Any = None,
    ) -> bool:
        """Um tique deste controle; ``True`` quando o jogo cala e a pessoa joga."""
        if not jogo:
            self.esquecer(uniq)
            return False
        if self._vibrou(uniq, vpad) or uniq not in self._calado_desde:
            self._calado_desde[uniq] = agora
        if rumble_em is not None and rumble_em > self._calado_desde[uniq]:
            self._calado_desde[uniq] = rumble_em
        if entrada is not None:
            mao = _assinatura_da_mao(entrada)
            antes = self._mao.get(uniq)
            if antes is None or _a_mao_mexeu(antes, mao):
                self._mao[uniq] = mao
                if antes is not None:
                    self._mexeu_em[uniq] = agora
        mexeu = self._mexeu_em.get(uniq)
        return (agora - self._calado_desde[uniq] >= SEM_RUMBLE_S
                and mexeu is not None and agora - mexeu <= ENTRADA_VIVA_S)


ECO_A_PARTIR_DE = 0.7


class AtuadorDaHaptica:
    """O toque do tiro, na forma que o controle escolheu, no tocador do rumble dele.

    Em «Do estilo» o toque é o do estilo. A escolha explícita dispara nos mesmos eventos da
    receita; o «—», o controle sem escolha e o Som no corpo (contínuo, do laço) não respondem a
    evento.
    O Toque toca na nota da unidade (a Assinatura, ``nota_de``) onde a Chegada vale.
    """

    canal = CANAL_HAPTICA

    def __init__(
        self,
        tocar: Callable[..., object],
        ouvindo: Callable[[], bool] | None = None,
        escolha_de: Callable[[str], str | None] | None = None,
        estilo_de: Callable[[], Any] | None = None,
        na_economia: Callable[[str], bool] | None = None,
        nota_de: Callable[[str], int | None] | None = None,
        acordada: Callable[[str], bool] | None = None,
        fator: Callable[[], float] | None = None,
    ) -> None:
        self._tocar = tocar
        self._fator = fator or (lambda: 1.0)
        self._acordada = acordada or (lambda uniq: False)
        self._ouvindo = ouvindo or (lambda: False)
        self._escolha_de = escolha_de or (lambda uniq: None)
        self._estilo_de = estilo_de or (lambda: None)
        self._na_economia = na_economia or (lambda uniq: False)
        self._nota_de = nota_de or (lambda uniq: None)

    def _toque_da_unidade(self, uniq: str) -> str:
        """O Toque na nota da cor do plástico (a Assinatura), na mesma regra da Chegada: todo
        estilo menos o Nativo e o Personalizado; o Toque de 160 Hz fora da regra ou sem nota."""
        from hefesto_dualsense4unix.daemon.subsystems.chegada import a_chegada_vale

        estilo = self._estilo_de()
        if not a_chegada_vale(estilo if isinstance(estilo, str) else None, False):
            return formas_de_haptica.TOQUE
        return formas_de_haptica.forma_da_nota(self._nota_de(uniq))

    def _forma(self, uniq: str) -> str | None:
        """A forma que toca neste controle agora; ``None`` quando ele não toca."""
        return formas_de_haptica.forma_que_vale(
            self._escolha_de(uniq), self._estilo_de(), bool(self._na_economia(uniq)))

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        escolha = formas_de_haptica.escolha_que_vale(
            self._escolha_de(evento.uniq), self._estilo_de())
        if escolha == formas_de_haptica.SEM_EFEITO or escolha in formas_de_haptica.CONTINUAS:
            return False
        do_estilo = escolha == formas_de_haptica.DO_ESTILO
        forma_do_estilo = formas_de_haptica.forma_do_estilo(self._estilo_de())
        if do_estilo and (forma_do_estilo == formas_de_haptica.SEM_EFEITO
                          or forma_do_estilo in formas_de_haptica.CONTINUAS):
            return False
        if evento.tipo == TIPO_SOM:
            if receita.som_quando_o_jogo_cala:
                return self._acordada(evento.uniq)
            return receita.lado_do_som
        quer = receita.vibracao_por_tiro or not do_estilo
        if evento.tipo != TIPO_RUMBLE or not quer:
            return False
        if receita.som_quando_o_jogo_cala:
            return True
        return not (receita.lado_do_som and self._ouvindo())

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        forma = self._forma(evento.uniq)
        if forma is None:
            return None
        pedido = (
            evento.uniq,
            evento.energia * receita.forca_do_toque * self._fator(),
            evento.lado,
            receita.duracao_do_toque_ms,
        )
        if forma == formas_de_haptica.ECO and evento.energia < ECO_A_PARTIR_DE:
            forma = formas_de_haptica.IMPACTO
        if forma == formas_de_haptica.TOQUE:
            forma = self._toque_da_unidade(evento.uniq)
        if forma == formas_de_haptica.TOQUE:
            self._tocar(*pedido)
        else:
            self._tocar(*pedido, forma)
        return None

    def devolver(self, uniq: str, agora: float) -> None:
        return None


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
        return None

    def devolver(self, uniq: str, agora: float) -> None:
        return None


GATILHO_ARMA = "arma"
GATILHO_RAJADA = "rajada"
RITMO_DA_ARMA_S = 0.25
RITMO_DA_RAJADA_S = 0.11
MESMO_TIRO_S = 0.05
CICLO_DO_GATILHO_S = 0.032
VOLTA_DO_GATILHO_S = 1.5
_PRESET_DO_GATILHO = {
    GATILHO_ARMA: "SemiAutoGun",
    GATILHO_RAJADA: "MultiPositionVibration",
}
_LADO_DO_BACKEND = {LADO_ESQUERDO: "left", LADO_DIREITO: "right"}
ACIONAMENTOS_DE_ARMA = frozenset({"Weapon", "Machine"})


def _padroes_do_modo(nome: str) -> dict[str, int]:
    """Os números de partida de um modo da tela (`trigger_specs.PRESETS`)."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    spec = get_spec(nome)
    return {p.name: p.default for p in spec.params} if spec is not None else {}


def _bloco_cru(nome: str, valores: Mapping[str, int]) -> bytes:
    """O bloco cru de 11 bytes de um modo com estes números, no layout que o relatório leva."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    return _bloco_do_efeito(build_from_name(nome, {**_padroes_do_modo(nome), **valores}))


def _bloco_do_efeito(efeito: Any) -> bytes:
    """O bloco cru de 11 bytes de um efeito pronto, no layout que o relatório leva."""
    f = efeito.forces
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


def lados_da_arma(estilo: str | None) -> frozenset[str]:
    """Os lados cujo acionamento do estilo é uma arma (Disparo ou Metralhadora): os do ritmo."""
    if not estilo:
        return frozenset()
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    chave = str(chave_do_catalogo(estilo))
    return frozenset(
        lado for lado in _LADO_DO_BACKEND
        if _modo_de_hoje_do_estilo(chave, lado) in ACIONAMENTOS_DE_ARMA)


def _lados_do_ritmo(
    arma_de: Callable[[str, str], bytes | None] | None, uniq: str
) -> Collection[str]:
    """Onde o ritmo do tiro escreve neste controle: os lados com arma; sem fonte, os dois."""
    if arma_de is None:
        return _LADO_DO_BACKEND.keys()
    return [lado for lado in _LADO_DO_BACKEND if arma_de(uniq, lado) is not None]


def arma_do_estilo(estilo: str | None, lado: str) -> tuple[str, dict[str, int]] | None:
    """O acionamento e os números que o estilo põe num lado, como o perfil os guarda.

    Com imersão no ``Lado``, os da imersão (com a variante do estilo); sem imersão, o lado do
    acionamento do estilo leva os ``ajustes_do_gatilho`` da receita e o outro, os de partida.
    """
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE, chave_do_catalogo

    dele = POR_CHAVE.get(str(chave_do_catalogo(estilo))) if estilo else None
    lado_do_estilo = getattr(dele, "l2" if lado == LADO_ESQUERDO else "r2", None)
    if dele is None or lado_do_estilo is None:
        return None
    invisivel = dele.receita_invisivel
    numeros: dict[str, int] = (
        dict(invisivel.ajustes_do_gatilho)
        if invisivel is not None and lado_do_estilo.modo == dele.gatilho else {})
    imersao = POR_CHAVE_DE_IMERSAO.get(lado_do_estilo.imersao or "")
    if imersao is not None:
        numeros = ajustes_da_imersao(imersao, lado_do_estilo.modo, dele.chave) or numeros
    return lado_do_estilo.modo, numeros


def bloco_do_gatilho(modo: str, receita: Receita, arma: bytes | None = None) -> bytes:
    """O bloco cru de 11 bytes, no layout que o relatório leva.

    A rajada é a vibração oficial na frequência da receita; a arma é a do lado no perfil
    (:class:`ArmasDoGatilho`); sem arma dada, a semi-automática da tela.
    """
    if modo == GATILHO_RAJADA:
        return _bloco_cru(
            _PRESET_DO_GATILHO[modo], {"frequency": receita.frequencia_da_rajada_hz})
    return arma if arma is not None else _bloco_cru(_PRESET_DO_GATILHO[modo], {})


def bloco_do_clique() -> bytes:
    """O bloco cru do Clique · mouse (o clique raso do começo do curso): o da Chegada."""
    from hefesto_dualsense4unix.profiles.efeitos_de_imersao import POR_CHAVE, ajustes_da_imersao

    return _bloco_cru("Weapon", ajustes_da_imersao(POR_CHAVE["clique-mouse"], "Weapon") or {})


class AtuadorDoGatilho:
    """Arma ou rajada, por controle, conforme o intervalo entre tiros.

    Escreve só no lado em que o perfil põe uma arma naquele controle (``arma_de``), e a arma sai
    com os números dele.
    """

    canal = CANAL_GATILHO

    def __init__(
        self,
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], object],
        apertado: Callable[[str, str], bool] | None = None,
        largar: Callable[[str], object] | None = None,
        cede: Callable[[str, str], bool] | None = None,
        soltar_lado: Callable[[str, str, bytes], object] | None = None,
        arma_de: Callable[[str, str], bytes | None] | None = None,
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        self._cede = cede
        self._soltar_lado = soltar_lado
        self._arma_de = arma_de
        self._bloco_escrito: dict[tuple[str, str], bytes] = {}
        self._ultimo_tiro: dict[tuple[str, str], float] = {}
        self._desejado: dict[tuple[str, str], str] = {}
        self._escrito: dict[tuple[str, str], str] = {}
        self._escreveu_em: dict[str, float] = {}

    def _lados(self, evento: Evento) -> list[str]:
        lados: list[str] = []
        if evento.tipo == TIPO_DEDO:
            lados = [evento.lado] if evento.lado in _LADO_DO_BACKEND else []
        elif evento.tipo == TIPO_RUMBLE and self.apertado is not None:
            lados = [lado for lado in _LADO_DO_BACKEND if self.apertado(evento.uniq, lado)]
        do_ritmo = _lados_do_ritmo(self._arma_de, evento.uniq)
        lados = [lado for lado in lados if lado in do_ritmo]
        if self._cede is None:
            return lados
        return [lado for lado in lados if not self._cede(evento.uniq, lado)]

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
            for lado in _lados_do_ritmo(self._arma_de, uniq)
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
            arma = self._arma_de(evento.uniq, lado) if self._arma_de is not None else None
            bloco = bloco_do_gatilho(modo, receita, arma)
            self._escrever(evento.uniq, _LADO_DO_BACKEND[lado], bloco)
            self._escrito[(evento.uniq, lado)] = modo
            self._bloco_escrito[(evento.uniq, lado)] = bloco
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

    def _esquecer(self, uniq: str) -> dict[str, bytes]:
        """Esquece o que o ritmo escreveu e devolve, por lado, o último bloco dele."""
        blocos: dict[str, bytes] = {}
        for lado, disco in _LADO_DO_BACKEND.items():
            self._escrito.pop((uniq, lado), None)
            bloco = self._bloco_escrito.pop((uniq, lado), None)
            if bloco is not None:
                blocos[disco] = bloco
        self._escreveu_em.pop(uniq, None)
        return blocos

    def devolver(self, uniq: str, agora: float) -> None:
        blocos = self._esquecer(uniq)
        if self._devolver(uniq) or self._soltar_lado is None:
            return
        for disco, bloco in blocos.items():
            self._soltar_lado(uniq, disco, bloco)


QUANDO_AO_APERTAR = "ao_apertar"
QUANDO_SEGURANDO = "segurando"
QUANDO_SEMPRE = "sempre"
TETO_DO_SEMPRE_S = 300.0
CANAL_DO_MOMENTO = "momento"


@dataclass(frozen=True)
class PlanoDoGatilho:
    """A imersão de um lado de um controle: o acionamento, os números e os momentos dele."""

    imersao: Imersao
    modo: str
    estilo: str
    ajustes: Mapping[str, int]
    momentos: tuple[Momento, ...]
    automatico: bool = False

    def bloco_da_volta(self, economia: bool = False) -> bytes:
        """O gatilho estático que o perfil põe no aparelho, para a volta de um lado só.

        Na Bateria longa é o bloco de economia (a mesma força que o perfil leva ao aparelho).
        """
        if self.automatico:
            return _bloco_cru("Off", {})
        if economia:
            return _bloco_cru(self.modo, _ajustes_na_economia(self.modo, self.ajustes))
        return _bloco_cru(self.modo, self.ajustes)


def _ajustes_na_economia(modo: str, ajustes: Mapping[str, int]) -> dict[str, int]:
    """Os números do acionamento com a força da economia: a mesma conta do perfil."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import (
        get_spec,
        preset_to_positional_params,
    )
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, gatilho_na_economia

    spec = get_spec(modo)
    if spec is None:
        return dict(ajustes)
    cheios = {**_padroes_do_modo(modo), **ajustes}
    try:
        posicionais = list(preset_to_positional_params(spec, cheios))
        reduzido = gatilho_na_economia(TriggerConfig(mode=modo, params=posicionais)).params
    except Exception:
        logger.debug("tato_vivo_economia_ilegivel", modo=modo, exc_info=True)
        return dict(ajustes)
    if len(reduzido) != len(spec.params):
        return dict(ajustes)
    numeros = [v for v in reduzido if isinstance(v, int)]
    if len(numeros) != len(reduzido):
        return dict(ajustes)
    return {p.name: v for p, v in zip(spec.params, numeros, strict=True)}


@dataclass(frozen=True)
class MapaDosMomentos:
    """Os planos do perfil ativo: os dos gatilhos globais e os de cada controle que os escreve."""

    geral: Mapping[str, PlanoDoGatilho] = field(default_factory=dict)
    por_controle: Mapping[str, Mapping[str, PlanoDoGatilho | None]] = field(
        default_factory=dict)

    def do(self, uniq: str, lado: str) -> PlanoDoGatilho | None:
        dele = self.por_controle.get(norm_mac(uniq) or "")
        if dele is not None and lado in dele:
            return dele[lado]
        return self.geral.get(lado)

    def __bool__(self) -> bool:
        return bool(self.geral) or any(
            plano is not None for dele in self.por_controle.values() for plano in dele.values())


SEM_MOMENTOS = MapaDosMomentos()


def _plano_do_lado(cfg: Any) -> PlanoDoGatilho | None:
    """O plano de um gatilho do perfil, se os números dele são de uma imersão com momentos.

    O perfil salvo com a chave que saiu da lista de onze (`SemiAutoGun`, `Rigid`…) passa pela
    mesma tradução da fábrica e da tela: o aparelho recebe o bloco da chave de hoje, a tela
    mostra a imersão da chave, e o motor toca os momentos. A volta à mão é o bloco do PERFIL,
    não o da imersão: com os números de ontem os dois diferem, e o aparelho fica como a tela.
    """
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
    from hefesto_dualsense4unix.core.trigger_effects import traduzir_chave_velha

    modo, params = _ler(cfg, "mode"), _ler(cfg, "params")
    if not isinstance(modo, str) or not isinstance(params, (list, tuple)):
        return None
    traduzida = traduzir_chave_velha(modo, list(params))
    if traduzida is not None:
        modo, params = traduzida
    achada = imersao_dos_numeros(modo, params)
    if achada is None:
        return None
    imersao, estilo = achada
    momentos = momentos_no_modo(imersao, modo)
    if not momentos:
        return None
    spec = get_spec(modo)
    ajustes = ajustes_da_imersao(imersao, modo, estilo) or {}
    if spec is not None and len(params) == len(spec.params):
        ajustes = {p.name: int(v) for p, v in zip(spec.params, params, strict=True)}
    return PlanoDoGatilho(imersao, modo, estilo, ajustes, momentos)


def _lado_do_estilo(estilo: str, lado: str) -> Any:
    """O ``Lado`` do estilo (``l2`` no esquerdo, ``r2`` no direito), ou ``None``."""
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

    return getattr(POR_CHAVE.get(estilo), "l2" if lado == LADO_ESQUERDO else "r2", None)


def _modo_de_hoje(modo: object) -> str | None:
    """O acionamento já na chave de hoje, ou ``None`` (nenhum).

    A chave que saiu da lista de onze (`AutoGun`, `PulseB`…) vale pelo acionamento de hoje,
    como a fábrica o leva ao aparelho.
    """
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
    from hefesto_dualsense4unix.core.trigger_effects import traduzir_chave_velha

    if not isinstance(modo, str) or not modo:
        return None
    spec = get_spec(modo)
    padroes = [p.default for p in spec.params] if spec is not None else []
    traduzida = traduzir_chave_velha(modo, padroes)
    return traduzida[0] if traduzida is not None else modo


def _modo_de_hoje_do_estilo(estilo: str, lado: str = LADO_DIREITO) -> str | None:
    """O acionamento que o estilo põe no gatilho de um lado, já na chave de hoje (``None``: nenhum).

    O direito é o ``gatilho`` do estilo (o modo do R2); o esquerdo é o do L2 (``Estilo.l2``).
    """
    dele = _lado_do_estilo(estilo, lado)
    return _modo_de_hoje(getattr(dele, "modo", None))


def _plano_do_automatico(estilo: str, lado: str = LADO_DIREITO) -> PlanoDoGatilho | None:
    """No Modo automático: a imersão com momentos que o estilo do jogo põe num dos lados.

    O ``Lado`` do estilo diz a imersão do gatilho (``R2`` e ``L2`` são receitas separadas); senão
    o lado fica no acionamento seco (o R2 do FPS é a Metralhadora, não a rajada que sobe). O estilo
    que saiu do catálogo (o Arco) vale pelo que o recebeu.
    """
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import chave_do_catalogo

    estilo = str(chave_do_catalogo(estilo))
    modo = _modo_de_hoje_do_estilo(estilo, lado)
    if modo is None:
        return None
    dele = _lado_do_estilo(estilo, lado)
    chave = getattr(dele, "imersao", None)
    imersao = POR_CHAVE_DE_IMERSAO.get(chave) if chave else None
    if imersao is None or modo not in imersao.ajustes or not momentos_no_modo(imersao, modo):
        return None
    return PlanoDoGatilho(imersao, modo, estilo, ajustes_da_imersao(imersao, modo, estilo) or {},
                          momentos_no_modo(imersao, modo), automatico=True)


def _lados_escritos(gatilhos: Any) -> frozenset[str]:
    """Os lados que um controle escreve por cima do global (`left`/`right`)."""
    if isinstance(gatilhos, Mapping):
        return frozenset(d for d in _LADO_DO_BACKEND.values() if gatilhos.get(d))
    escritos = getattr(gatilhos, "model_fields_set", None) or set()
    return frozenset(d for d in _LADO_DO_BACKEND.values() if d in escritos)


def _gatilhos_do_perfil(
    perfil: Any,
) -> tuple[Any, list[tuple[str, Any, frozenset[str]]], str] | None:
    """Os gatilhos do perfil, o que cada controle escreve por cima e o modo da aba.

    O modo é o do esquema (``decidir_o_modo_dos_gatilhos``). ``None`` quando o perfil não tem
    gatilhos. Os momentos e a vibração do gatilho leem por aqui: o modo tem uma fonte só.
    """
    gatilhos = _ler(perfil, "triggers") if perfil is not None else None
    if gatilhos is None:
        return None
    from hefesto_dualsense4unix.profiles.schema import (
        MODO_SEM_EFEITO_DO_GATILHO,
        decidir_o_modo_dos_gatilhos,
    )

    controles = _ler(perfil, "controllers")
    escritos: list[tuple[str, Any, frozenset[str]]] = []
    for chave, dele in (controles.items() if isinstance(controles, Mapping) else ()):
        seus = _ler(dele, "triggers")
        lados = _lados_escritos(seus) if seus is not None else frozenset()
        if lados:
            escritos.append((str(chave), seus, lados))
    todos = [_ler(gatilhos, d) for d in _LADO_DO_BACKEND.values()]
    todos += [_ler(seus, d) for _c, seus, lados in escritos for d in lados]
    sem_efeito = all(_ler(c, "mode") == MODO_SEM_EFEITO_DO_GATILHO for c in todos)
    escrito = _ler(gatilhos, "modo")
    modo = decidir_o_modo_dos_gatilhos(escrito if isinstance(escrito, str) else None, sem_efeito)
    return gatilhos, escritos, modo


def _suspensos(perfil: Any, modo: str, vivas: frozenset[str]) -> tuple[bool, frozenset[str]]:
    """O modo de extensão viva suspende o efeito fixo dos gatilhos: no perfil inteiro e nos
    controles que o escrevem por cima; com a extensão fora, vale o personalizado."""
    from hefesto_dualsense4unix.profiles.schema import extensao_do_modo, modo_que_vale

    def suspende(escrito: Any) -> bool:
        return extensao_do_modo(modo_que_vale(escrito if isinstance(escrito, str) else None,
                                              vivas)) is not None

    controles = _ler(perfil, "controllers")
    seus = frozenset(
        alvo for chave, dele in (controles.items() if isinstance(controles, Mapping) else ())
        if (alvo := norm_mac(str(chave))) and suspende(_ler(_ler(dele, "triggers"), "modo")))
    return suspende(modo), seus


def planos_do_perfil(perfil: Any, vivas: frozenset[str] = frozenset()) -> MapaDosMomentos:
    """Os planos dos momentos de um perfil: por lado, por controle, e o do automático.

    O modo da aba é o do esquema (`decidir_o_modo_dos_gatilhos`): no automático, os dois
    lados de todo controle tocam a imersão que o estilo do perfil põe na frente, com a
    variante dele; no personalizado, cada lado toca a imersão que os números dele dizem.
    """
    lidos = _gatilhos_do_perfil(perfil)
    if lidos is None:
        return SEM_MOMENTOS
    gatilhos, escritos, modo = lidos
    from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO

    todo, calados = _suspensos(perfil, modo, vivas)
    mudos: dict[str, dict[str, PlanoDoGatilho | None]] = {
        alvo: dict.fromkeys(_LADO_DO_BACKEND) for alvo in calados}
    if todo:
        return MapaDosMomentos({}, mudos)
    if modo == MODO_AUTOMATICO:
        estilo = _ler(perfil, "estilo")
        if not isinstance(estilo, str):
            return MapaDosMomentos({}, mudos) if mudos else SEM_MOMENTOS
        planos = {lado: _plano_do_automatico(estilo, lado) for lado in _LADO_DO_BACKEND}
        return MapaDosMomentos({lado: p for lado, p in planos.items() if p is not None}, mudos)
    geral = {lado: plano for lado, disco in _LADO_DO_BACKEND.items()
             if (plano := _plano_do_lado(_ler(gatilhos, disco))) is not None}
    por_controle: dict[str, dict[str, PlanoDoGatilho | None]] = {}
    for chave, seus, lados in escritos:
        alvo = norm_mac(chave)
        if alvo:
            por_controle[alvo] = {lado: _plano_do_lado(_ler(seus, disco))
                                  for lado, disco in _LADO_DO_BACKEND.items() if disco in lados}
    return MapaDosMomentos(geral, {**por_controle, **mudos})


MODOS_QUE_VIBRAM = frozenset(FAMILIAS["metralhadora"]) | frozenset(
    FAMILIAS["vibração por posição"])


@dataclass(frozen=True)
class VibracaoDoGatilho:
    """Em que controles o gatilho do perfil vibra (algum dos dois lados)."""

    geral: bool = False
    por_controle: Mapping[str, bool] = field(default_factory=dict)

    def de(self, uniq: str) -> bool:
        dele = self.por_controle.get(norm_mac(uniq) or "")
        return self.geral if dele is None else dele


SEM_VIBRACAO = VibracaoDoGatilho()


def _o_gatilho_vibra(cfg: Any) -> bool:
    """O gatilho (um lado do perfil) está num acionamento que vibra, na chave de hoje."""
    from hefesto_dualsense4unix.core.trigger_effects import traduzir_chave_velha

    modo, params = _ler(cfg, "mode"), _ler(cfg, "params")
    if not isinstance(modo, str):
        return False
    if isinstance(params, (list, tuple)):
        traduzida = traduzir_chave_velha(modo, list(params))
        if traduzida is not None:
            modo = traduzida[0]
    return modo in MODOS_QUE_VIBRAM


def vibracao_do_gatilho_do_perfil(
    perfil: Any, vivas: frozenset[str] = frozenset(),
) -> VibracaoDoGatilho:
    """Onde o gatilho do perfil vibra: no automático, o acionamento do estilo; senão, o escrito."""
    lidos = _gatilhos_do_perfil(perfil)
    if lidos is None:
        return SEM_VIBRACAO
    gatilhos, escritos, modo = lidos
    from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO

    todo, calados = _suspensos(perfil, modo, vivas)
    if todo or calados:
        base = SEM_VIBRACAO if todo else vibracao_do_gatilho_do_perfil(perfil)
        return VibracaoDoGatilho(
            base.geral, {**base.por_controle, **dict.fromkeys(calados, False)})
    if modo == MODO_AUTOMATICO:
        estilo = _ler(perfil, "estilo")
        de_hoje = (
            [_modo_de_hoje_do_estilo(estilo, lado) for lado in _LADO_DO_BACKEND]
            if isinstance(estilo, str) else [])
        return VibracaoDoGatilho(geral=any(m in MODOS_QUE_VIBRAM for m in de_hoje if m))
    geral = {disco: _o_gatilho_vibra(_ler(gatilhos, disco)) for disco in _LADO_DO_BACKEND.values()}
    por_controle: dict[str, bool] = {}
    for chave, seus, lados in escritos:
        alvo = norm_mac(chave)
        if alvo:
            por_controle[alvo] = any(
                _o_gatilho_vibra(_ler(seus, disco)) if disco in lados else vibra
                for disco, vibra in geral.items())
    return VibracaoDoGatilho(any(geral.values()), por_controle)


@dataclass(frozen=True)
class ArmasDoGatilho:
    """O bloco da arma de cada lado em que o perfil ativo põe uma: os lados do ritmo do tiro."""

    geral: Mapping[str, bytes] = field(default_factory=dict)
    por_controle: Mapping[str, Mapping[str, bytes | None]] = field(default_factory=dict)

    def de(self, uniq: str, lado: str) -> bytes | None:
        dele = self.por_controle.get(norm_mac(uniq) or "")
        if dele is not None and lado in dele:
            return dele[lado]
        return self.geral.get(lado)


SEM_ARMAS = ArmasDoGatilho()


def _arma_do_lado(cfg: Any) -> bytes | None:
    """O bloco de um gatilho do perfil, se o acionamento dele (na chave de hoje) é uma arma."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name, traduzir_chave_velha

    modo, params = _ler(cfg, "mode"), _ler(cfg, "params")
    if not isinstance(modo, str) or not isinstance(params, (list, tuple)):
        return None
    traduzida = traduzir_chave_velha(modo, list(params))
    if traduzida is not None:
        modo, params = traduzida
    if modo not in ACIONAMENTOS_DE_ARMA:
        return None
    return _bloco_do_efeito(build_from_name(modo, list(params)))


def armas_do_gatilho_do_perfil(
    perfil: Any, vivas: frozenset[str] = frozenset(),
) -> ArmasDoGatilho:
    """Onde o ritmo do tiro escreve, e com que arma: o que o perfil põe em cada gatilho.

    No automático, o lado em que o estilo põe uma arma, com os números do estilo; no
    personalizado, o lado (global ou de cada controle) que a aba deixou numa arma, com os
    números escritos.
    """
    lidos = _gatilhos_do_perfil(perfil)
    from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO

    if lidos is not None:
        todo, calados = _suspensos(perfil, lidos[2], vivas)
        if todo or calados:
            base = SEM_ARMAS if todo else armas_do_gatilho_do_perfil(perfil)
            mudas: dict[str, dict[str, bytes | None]] = {
                alvo: dict.fromkeys(_LADO_DO_BACKEND) for alvo in calados}
            return ArmasDoGatilho(base.geral, {**base.por_controle, **mudas})
    if lidos is None or lidos[2] == MODO_AUTOMATICO:
        estilo = _ler(perfil, "estilo")
        if not isinstance(estilo, str):
            return SEM_ARMAS
        armas = {lado: arma_do_estilo(estilo, lado) for lado in lados_da_arma(estilo)}
        return ArmasDoGatilho({lado: _bloco_cru(*a) for lado, a in armas.items() if a})
    gatilhos, escritos, _modo = lidos
    geral = {lado: arma for lado, disco in _LADO_DO_BACKEND.items()
             if (arma := _arma_do_lado(_ler(gatilhos, disco))) is not None}
    por_controle: dict[str, dict[str, bytes | None]] = {}
    for chave, seus, lados in escritos:
        alvo = norm_mac(chave)
        if alvo:
            por_controle[alvo] = {lado: _arma_do_lado(_ler(seus, disco))
                                  for lado, disco in _LADO_DO_BACKEND.items() if disco in lados}
    return ArmasDoGatilho(geral, por_controle)


def momentos_em_efeito(
    momentos: Sequence[Momento],
    desde_o_aperto: float | None,
    desde_sempre: float | None,
    agora: float,
    *,
    desde_o_clique: float | None = None,
    sem_status: bool = True,
) -> tuple[tuple[int, int], ...]:
    """``(índice, repetição)`` de cada momento que vale agora, na ordem em que se sobrepõem.

    A origem do «ao apertar», do «segurando» e do «pronto» é o aperto (soltar acaba com eles);
    a do «sempre», a hora em que a imersão passou a valer naquele lado. O «passou do clique»
    nasce do instante em que o status do Disparo chegou a 2 (``desde_o_clique``); sem o status
    (``sem_status``), cai no relógio do aperto, e o ``apos_ms`` dele é esse relógio. O «sempre»
    sem ``dura_ms`` expira em ``TETO_DO_SEMPRE_S``. A repetição só diz em que volta o momento
    está: quem escreve olha o bloco, não a repetição.
    """
    vale: list[tuple[int, int]] = []
    for indice, momento in enumerate(momentos):
        espera_ms = float(momento.apos_ms)
        if momento.quando == QUANDO_SEMPRE:
            origem = desde_sempre
        elif momento.quando == QUANDO_PASSOU_DO_CLIQUE and not sem_status:
            origem, espera_ms = desde_o_clique, 0.0
        else:
            origem = desde_o_aperto
        if origem is None:
            continue
        if (momento.quando == QUANDO_SEMPRE and momento.dura_ms is None
                and agora - origem >= TETO_DO_SEMPRE_S):
            continue
        passou_ms = (agora - origem) * 1000.0 - espera_ms
        if passou_ms < 0:
            continue
        repeticao = 0
        if momento.a_cada_ms:
            repeticao = int(passou_ms // momento.a_cada_ms)
            passou_ms -= repeticao * momento.a_cada_ms
        if momento.dura_ms is not None and passou_ms >= momento.dura_ms:
            continue
        vale.append((indice, repeticao))
    return tuple(vale)


def bloco_do_momento(plano: PlanoDoGatilho, indices: Iterable[int]) -> bytes:
    """O bloco com os momentos sobrepostos: o mesmo modo ajusta os números do perfil.

    O «pronto» vai por último, qualquer que seja a ordem: ele toma o gatilho por cima do resto.
    """
    modo, valores = plano.modo, dict(plano.ajustes)
    ordem = sorted(indices, key=lambda i: plano.momentos[i].quando == QUANDO_PRONTO)
    for indice in ordem:
        momento = plano.momentos[indice]
        if momento.modo != modo:
            modo = momento.modo
            valores = dict(ajustes_da_imersao(plano.imersao, modo, plano.estilo) or {})
        valores.update(momento.ajustes)
    return _bloco_cru(modo, valores)


class AtuadorDosMomentos:
    """Os momentos da imersão de cada lado de cada controle, no relógio do motor.

    A cada tique o motor lhe dá a mesa (``relogio``). Escreve quando o BLOCO muda (a volta do
    ``a_cada_ms`` não reescreve o mesmo bloco: o ritmo é do firmware) e volta ao estático
    quando nenhum momento vale: o lado só, à mão; o último, pela sessão. Entre as batidas de
    um «sempre» que se repete a sessão fica. Toda saída passa por ``devolver``: motor parado
    ou calado, Bateria longa e «sempre» que expirou.
    """

    canal = CANAL_GATILHO

    def __init__(
        self,
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], bool],
        apertado: Callable[[str, str], bool],
        largar: Callable[[str], object] | None = None,
        na_economia: Callable[[str], bool] | None = None,
        disparo: Callable[[str, str], int | None] | None = None,
        cede: Callable[[str, str, float], bool] | None = None,
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        self._na_economia = na_economia
        self._cede = cede
        self._disparo = disparo
        self._aperto: dict[tuple[str, str], float] = {}
        self._clique: dict[tuple[str, str], float] = {}
        self._sempre: dict[tuple[str, str], tuple[PlanoDoGatilho, float]] = {}
        self._expirou: set[tuple[str, str]] = set()
        self._escrito: dict[tuple[str, str], bytes] = {}
        self._planos: dict[tuple[str, str], PlanoDoGatilho] = {}
        self._entre_batidas: set[str] = set()

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        return False

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        return None

    def segura(self, uniq: str) -> list[str]:
        """Os lados deste controle em que um momento está escrito."""
        return [lado for lado in _LADO_DO_BACKEND if (uniq, lado) in self._escrito]

    def _repete(self, uniq: str) -> bool:
        """Algum lado deste controle tem um «sempre» que se repete: a próxima batida vem."""
        return any(
            u == uniq and (u, lado) not in self._expirou
            and any(m.quando == QUANDO_SEMPRE and m.a_cada_ms for m in plano.momentos)
            for (u, lado), (plano, _desde) in self._sempre.items())

    def _na_sessao(self, uniq: str) -> bool:
        return bool(self.segura(uniq)) or uniq in self._entre_batidas

    def _economia(self, uniq: str) -> bool:
        return self._na_economia is not None and bool(self._na_economia(uniq))

    def relogio(
        self,
        motor: TatoVivo,
        agora: float,
        uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        planos = motor.momentos if receita.momentos_da_imersao else SEM_MOMENTOS
        escritas = 0
        for saiu in ({u for u, _lado in self._escrito} | self._entre_batidas) - set(uniqs):
            self.soltar(saiu)
        for uniq in uniqs:
            estado = estado_de(uniq)
            if estado is None or not decidir(CANAL_GATILHO, estado):
                if estado is not None and _o_modo_cala_o_motor(estado):
                    self.devolver(uniq, agora)
                elif self._na_sessao(uniq):
                    motor.contadores["soltos_ao_jogo"] += 1
                    self.soltar(uniq)
                self._ver_o_dedo(uniq, agora)
                continue
            escritas += self._tocar(motor, uniq, planos, agora)
        return escritas

    def _ver_o_dedo(self, uniq: str, agora: float) -> None:
        for lado in _LADO_DO_BACKEND:
            chave = (uniq, lado)
            if self.apertado(uniq, lado):
                self._aperto.setdefault(chave, agora)
                status = self._disparo(uniq, lado) if self._disparo is not None else None
                if (status is not None and status >= TRIGGER_ESTADO_DISPAROU
                        and chave not in self._clique):
                    self._clique[chave] = agora
            else:
                self._aperto.pop(chave, None)
                self._clique.pop(chave, None)

    def _tocar(self, motor: TatoVivo, uniq: str, planos: MapaDosMomentos, agora: float) -> int:
        self._ver_o_dedo(uniq, agora)
        economia = self._economia(uniq)
        escritas = 0
        a_voltar: list[str] = []
        cedeu = False
        for lado, disco in _LADO_DO_BACKEND.items():
            chave = (uniq, lado)
            if self._cede is not None and self._cede(uniq, lado, agora):
                if self._escrito.pop(chave, None) is not None:
                    self._planos.pop(chave, None)
                    cedeu = True
                continue
            plano = None if economia else planos.do(uniq, lado)
            if plano is None:
                self._sempre.pop(chave, None)
                self._expirou.discard(chave)
                if chave in self._escrito:
                    a_voltar.append(lado)
                continue
            visto = self._sempre.get(chave)
            if visto is None or visto[0] != plano:
                self._sempre[chave] = (plano, agora)
                self._expirou.discard(chave)
            desde = self._sempre[chave][1]
            if agora - desde >= TETO_DO_SEMPRE_S and any(
                    m.quando == QUANDO_SEMPRE and m.dura_ms is None for m in plano.momentos):
                self._expirou.add(chave)
            sem_status = self._disparo is None or self._disparo(uniq, lado) is None
            vale = momentos_em_efeito(
                plano.momentos, self._aperto.get(chave), desde, agora,
                desde_o_clique=self._clique.get(chave), sem_status=sem_status)
            if not vale:
                if chave in self._escrito:
                    a_voltar.append(lado)
                continue
            bloco = bloco_do_momento(plano, (i for i, _rep in vale))
            if self._escrito.get(chave) == bloco:
                continue
            if not motor.teto.cabe(uniq, agora):
                motor.contadores["recusas_do_teto"] += 1
                continue
            motor.teto.gastar(uniq, agora)
            self._escrever(uniq, disco, bloco)
            self._escrito[chave] = bloco
            self._planos[chave] = plano
            escritas += 1
            motor.contadores["escritas"] += 1
        if a_voltar:
            self._voltar(uniq, a_voltar)
            motor.contadores["devolucoes"] += 1
        elif uniq in self._entre_batidas and not self._repete(uniq):
            self._voltar(uniq, ())
            motor.contadores["devolucoes"] += 1
        if cedeu and not self._na_sessao(uniq) and self._largar is not None:
            self._largar(uniq)
        return escritas

    def _voltar(self, uniq: str, lados: Sequence[str]) -> None:
        """O lado volta ao estático: à mão se o motor segura mais algo, pela sessão se não."""
        estaticos: dict[str, bytes] = {}
        economia = self._economia(uniq)
        for lado in lados:
            self._escrito.pop((uniq, lado), None)
            plano = self._planos.pop((uniq, lado), None)
            if plano is not None:
                estaticos[lado] = plano.bloco_da_volta(economia)
        if self.segura(uniq) or self._repete(uniq):
            for lado, bloco in estaticos.items():
                self._escrever(uniq, _LADO_DO_BACKEND[lado], bloco)
            if self._repete(uniq):
                self._entre_batidas.add(uniq)
            return
        self._entre_batidas.discard(uniq)
        if self._devolver(uniq):
            return
        for lado, bloco in estaticos.items():
            self._escrever(uniq, _LADO_DO_BACKEND[lado], bloco)
        if self._largar is not None:
            self._largar(uniq)

    def soltar(self, uniq: str) -> None:
        """O jogo tomou o gatilho: o que o motor escreveu deixou de valer."""
        for lado in _LADO_DO_BACKEND:
            chave = (uniq, lado)
            self._escrito.pop(chave, None)
            self._planos.pop(chave, None)
            self._sempre.pop(chave, None)
            self._expirou.discard(chave)
        self._entre_batidas.discard(uniq)
        if self._largar is not None:
            self._largar(uniq)

    def devolver(self, uniq: str, agora: float) -> None:
        """O ponto único de devolução: o controle volta ao perfil, sem plano que o segure.

        Quem o chama (motor parado, motor calado) quer o gatilho de volta ao perfil e o «sempre»
        recomeçando depois: por isso as batidas e o teto de 5 minutos zeram antes da volta.
        """
        for lado in _LADO_DO_BACKEND:
            chave = (uniq, lado)
            self._sempre.pop(chave, None)
            self._expirou.discard(chave)
            self._clique.pop(chave, None)
        if self._na_sessao(uniq):
            self._voltar(uniq, self.segura(uniq))

    def devolver_tudo(self, agora: float) -> None:
        """O motor parou: cada controle em que o momento segura a sessão volta ao perfil."""
        self._aperto.clear()
        for uniq in {u for u, _lado in self._escrito} | set(self._entre_batidas):
            self.devolver(uniq, agora)


CANAL_DO_DEDO = "dedo_do_rumble"
DEGRAUS_DO_DEDO = 8
SEM_RUMBLE_NO_DEDO_S = 0.150
HISTERESE_DO_DEDO = 1
FREQUENCIA_DO_DEDO_HZ = 40


def degrau_do_rumble(fraco: int, forte: int) -> int:
    """O degrau (1 a 8) do par cru do jogo; 0 com o jogo calado."""
    if calado(fraco, forte):
        return 0
    nivel = max(int(fraco), int(forte))
    return max(1, min(DEGRAUS_DO_DEDO, -(-nivel * DEGRAUS_DO_DEDO // 255)))


def fica_no_degrau(nivel: int, escrito: int) -> bool:
    """O nível cru (0 a 255) ainda cabe no degrau escrito, com a histerese em volta dele."""
    largura = 255 / DEGRAUS_DO_DEDO
    folga = HISTERESE_DO_DEDO * largura / 2
    return (escrito - 1) * largura - folga < nivel <= escrito * largura + folga


def bloco_do_dedo(degrau: int) -> bytes:
    """O bloco cru da vibração no curso inteiro, com a amplitude do degrau."""
    from hefesto_dualsense4unix.core.trigger_effects import vibration

    amplitude = max(1, min(DEGRAUS_DO_DEDO, int(degrau)))
    return _bloco_do_efeito(vibration(0, amplitude, FREQUENCIA_DO_DEDO_HZ))


class AtuadorDoDedo:
    """O rumble do jogo no dedo que aperta o gatilho, lado a lado e controle a controle.

    Anda no relógio do motor: a cada tique olha a mesa. O lado vibra enquanto o dedo está além
    do disparo e o jogo vibra (ou vibrou há menos de ``SEM_RUMBLE_NO_DEDO_S``); a soltura, o fim
    do rumble, o jogo que escreve o gatilho, um momento da imersão, o gatilho do perfil que já
    vibra e a Bateria longa devolvem o lado. Escreve só quando o degrau muda além da histerese,
    no máximo uma vez por ciclo do gatilho, dentro do teto; no rádio sem fatia livre, espera.
    """

    canal = CANAL_GATILHO

    def __init__(
        self,
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], bool],
        apertado: Callable[[str, str], bool],
        largar: Callable[[str], object] | None = None,
        cede: Callable[[str, str], bool] | None = None,
        soltar_lado: Callable[[str, str, bytes], object] | None = None,
        radio_cede: Callable[[str], bool] | None = None,
        arma_de: Callable[[str, str], bytes | None] | None = None,
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        self._cede = cede
        self._soltar_lado = soltar_lado
        self._radio_cede = radio_cede
        self._arma_de = arma_de
        self._degrau: dict[tuple[str, str], int] = {}
        self._bloco: dict[tuple[str, str], bytes] = {}
        self._escreveu_em: dict[str, float] = {}

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        return False

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        return None

    def segura(self, uniq: str) -> list[str]:
        """Os lados deste controle em que o rumble está no dedo."""
        return [lado for lado in _LADO_DO_BACKEND if (uniq, lado) in self._degrau]

    def _par_vivo(self, motor: TatoVivo, uniq: str, agora: float) -> tuple[int, int]:
        """O par cru que vale no dedo agora; ``(0, 0)`` com o jogo calado há 150 ms."""
        chave = norm_mac(uniq) or uniq
        par = motor.rumble_de_agora.get(chave)
        if par is None:
            return (0, 0)
        if calado(*par):
            forca_em = motor.rumble_com_forca_em.get(chave)
            if forca_em is None or agora - forca_em >= SEM_RUMBLE_NO_DEDO_S:
                return (0, 0)
            par = motor.par_com_forca.get(chave, par)
        return par

    def relogio(
        self,
        motor: TatoVivo,
        agora: float,
        uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        for saiu in {u for u, _lado in self._degrau} - set(uniqs):
            self.soltar(saiu)
        escritas = 0
        for uniq in uniqs:
            estado = estado_de(uniq)
            if estado is None or not decidir(CANAL_GATILHO, estado):
                if self.segura(uniq):
                    if estado is not None and not _o_modo_cala_o_motor(estado):
                        motor.contadores["soltos_ao_jogo"] += 1
                        self.soltar(uniq)
                    else:
                        self.devolver(uniq, agora)
                continue
            do_ritmo = (
                _lados_do_ritmo(self._arma_de, uniq) if receita.gatilho_no_ritmo else ())
            if not receita.rumble_no_dedo or len(do_ritmo) == len(_LADO_DO_BACKEND):
                if self.segura(uniq):
                    self.devolver(uniq, agora)
                continue
            escritas += self._tocar(motor, uniq, agora, do_ritmo)
        return escritas

    def _tocar(
        self, motor: TatoVivo, uniq: str, agora: float, do_ritmo: Collection[str] = ()
    ) -> int:
        par = self._par_vivo(motor, uniq, agora)
        degrau, nivel = degrau_do_rumble(*par), max(par)
        a_voltar: list[str] = []
        escritas = 0
        for lado, disco in _LADO_DO_BACKEND.items():
            chave = (uniq, lado)
            quer = (degrau > 0 and self.apertado(uniq, lado) and lado not in do_ritmo
                    and not (self._cede is not None and self._cede(uniq, lado)))
            if not quer:
                if chave in self._degrau:
                    a_voltar.append(lado)
                continue
            escrito = self._degrau.get(chave)
            if escrito is not None and fica_no_degrau(nivel, escrito):
                continue
            ultima = self._escreveu_em.get(uniq)
            if ultima is not None and agora - ultima < CICLO_DO_GATILHO_S:
                continue
            if self._radio_cede is not None and self._radio_cede(uniq):
                motor.contadores["recusas_do_radio"] = (
                    motor.contadores.get("recusas_do_radio", 0) + 1)
                continue
            if not motor.teto.cabe(uniq, agora):
                motor.contadores["recusas_do_teto"] += 1
                continue
            motor.teto.gastar(uniq, agora)
            bloco = bloco_do_dedo(degrau)
            self._escrever(uniq, disco, bloco)
            self._degrau[chave] = degrau
            self._bloco[chave] = bloco
            escritas += 1
            motor.contadores["escritas"] += 1
        if escritas:
            self._escreveu_em[uniq] = agora
        if a_voltar:
            self._voltar(uniq, a_voltar)
            motor.contadores["devolucoes"] += 1
        return escritas

    def _voltar(self, uniq: str, lados: Sequence[str]) -> None:
        """O lado volta ao efeito do estilo: à mão se o outro lado segue no dedo, ou pela sessão."""
        blocos: dict[str, bytes] = {}
        for lado in lados:
            self._degrau.pop((uniq, lado), None)
            bloco = self._bloco.pop((uniq, lado), None)
            if bloco is not None:
                blocos[_LADO_DO_BACKEND[lado]] = bloco
        if not self.segura(uniq):
            self._escreveu_em.pop(uniq, None)
            if self._devolver(uniq):
                return
        if self._soltar_lado is not None:
            for disco, bloco in blocos.items():
                self._soltar_lado(uniq, disco, bloco)

    def soltar(self, uniq: str) -> None:
        """O jogo tomou o gatilho: o que o dedo escreveu deixou de valer."""
        for lado in _LADO_DO_BACKEND:
            self._degrau.pop((uniq, lado), None)
            self._bloco.pop((uniq, lado), None)
        self._escreveu_em.pop(uniq, None)
        if self._largar is not None:
            self._largar(uniq)

    def devolver(self, uniq: str, agora: float) -> None:
        """O controle volta ao efeito do estilo nos lados em que o rumble estava no dedo."""
        if self.segura(uniq):
            self._voltar(uniq, self.segura(uniq))

    def devolver_tudo(self, agora: float) -> None:
        """O motor parou: cada controle com o rumble no dedo volta ao estilo."""
        for uniq in {u for u, _lado in self._degrau}:
            self.devolver(uniq, agora)


COICES_POR_S = 3
JANELA_DO_COICE_S = 1.0
FORCA_NA_ECONOMIA = FORCA_DO_DEGRAU["economia"]
FOLGA_DA_VOLTA_S = 0.15
_MOTOR_DO_LADO = {
    LADO_ESQUERDO: padroes_de_vibracao.ESQUERDO,
    LADO_DIREITO: padroes_de_vibracao.DIREITO,
}


@dataclass
class _PadraoEmCurso:
    passos: tuple[padroes_de_vibracao.Passo, ...]
    inicio: float
    forca: float
    indice: int = -1
    escrito: tuple[int, int] | None = None


class AtuadorDosMotores:
    """Os dois motores do controle tocando o padrão escolhido, passo a passo, no relógio do motor.

    O padrão acaba em zero por construção, tem no máximo 2000 ms e não reinicia enquanto toca.
    """

    canal = CANAL_MOTORES

    def __init__(
        self,
        escrever: Callable[[str, int, int], object],
        padrao_de: Callable[[str], str | None],
        forca_de: Callable[[str], float],
        estilo_de: Callable[[], Any] | None = None,
        largar: Callable[[str], object] = lambda _uniq: None,
    ) -> None:
        self._escrever = escrever
        self._estilo_de = estilo_de or (lambda: None)
        self._padrao_de = padrao_de
        self._forca_de = forca_de
        self._largar = largar
        self._em_curso: dict[tuple[str, str], _PadraoEmCurso] = {}
        self._par: dict[str, tuple[int, int]] = {}
        self._coices: dict[str, deque[float]] = {}

    def _cabe_o_coice(self, uniq: str, instante: float) -> bool:
        fila = self._coices.setdefault(uniq, deque())
        while fila and instante - fila[0] >= JANELA_DO_COICE_S:
            fila.popleft()
        return len(fila) < COICES_POR_S

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if (evento.tipo not in (TIPO_DEDO, TIPO_SOM, TIPO_SOLTA)
                or (evento.uniq, _pista(evento)) in self._em_curso):
            return False
        padrao = self._padrao_de(evento.uniq)
        if padrao is None:
            return False
        regra = padroes_de_vibracao.na_soltura_do_estilo(padrao, self._estilo_de())
        if padrao in padroes_de_vibracao.NA_SOLTURA or regra is not None:
            if evento.tipo != TIPO_SOLTA:
                return False
            if regra is not None and (
                    evento.duracao_s < regra.segurado_s
                    or (regra.lado is not None and evento.lado != regra.lado)):
                return False
            return padrao not in padroes_de_vibracao.NA_SOLTURA or self._cabe_o_coice(
                evento.uniq, evento.instante)
        if padrao in padroes_de_vibracao.DO_LADO_DO_SOM:
            return evento.tipo == TIPO_SOM
        return evento.tipo == TIPO_DEDO

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        uniq = evento.uniq
        padrao = self._padrao_de(uniq)
        if padrao is None:
            return None
        if padrao in padroes_de_vibracao.NA_SOLTURA:
            self._coices.setdefault(uniq, deque()).append(evento.instante)
        pista = _pista(evento)
        passos = padroes_de_vibracao.sequencia(padrao, pista)
        self._em_curso[(uniq, pista)] = _PadraoEmCurso(passos, agora, self._forca_de(uniq))
        self._andar((uniq, pista), agora)
        return agora + padroes_de_vibracao.duracao_ms(padrao) / 1000.0 + FOLGA_DA_VOLTA_S

    def _andar(self, chave: tuple[str, str], agora: float) -> None:
        """Escreve o passo em que o relógio está; no fim, solta o padrão daquele lado."""
        curso = self._em_curso.get(chave)
        if curso is None:
            return
        decorrido_ms = (agora - curso.inicio) * 1000.0
        acumulado = 0
        for indice, (ms, esquerdo, direito) in enumerate(curso.passos):
            acumulado += ms
            if decorrido_ms < acumulado:
                if indice != curso.indice:
                    curso.indice = indice
                    curso.escrito = (_valor(direito, curso.forca), _valor(esquerdo, curso.forca))
                    self._escrever_o_par(chave[0])
                return
        del self._em_curso[chave]
        self._escrever_o_par(chave[0])

    def _cursos_de(self, uniq: str) -> list[tuple[str, str]]:
        return [chave for chave in self._em_curso if chave[0] == uniq]

    def _escrever_o_par(self, uniq: str) -> None:
        """Os dois lados de um controle saem num par só, o maior de cada motor."""
        escritos = [self._em_curso[c].escrito or (0, 0) for c in self._cursos_de(uniq)]
        par = (max((e[0] for e in escritos), default=0), max((e[1] for e in escritos), default=0))
        if par != self._par.get(uniq, (0, 0)):
            self._escrever(uniq, *par)
        self._par[uniq] = par

    def _zerar(self, uniq: str) -> None:
        for chave in self._cursos_de(uniq):
            del self._em_curso[chave]
        self._escrever_o_par(uniq)

    def relogio(
        self,
        motor: TatoVivo,
        agora: float,
        uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        escritas = 0
        for chave in list(self._em_curso):
            if chave[0] not in uniqs or estado_de(chave[0]) is None:
                self.soltar(chave[0])
                continue
            curso = self._em_curso.get(chave)
            if curso is None:
                continue
            antes = curso.indice
            self._andar(chave, agora)
            curso = self._em_curso.get(chave)
            if curso is None or curso.indice != antes:
                escritas += 1
                motor.contadores["escritas"] += 1
        return escritas

    def soltar(self, uniq: str) -> None:
        """O jogo tomou os motores: o padrão deixa de valer, sem escrever por cima do jogo."""
        for chave in self._cursos_de(uniq):
            del self._em_curso[chave]
        self._par.pop(uniq, None)
        self._largar(uniq)

    def devolver(self, uniq: str, agora: float) -> None:
        self._zerar(uniq)

    def devolver_tudo(self, agora: float) -> None:
        for uniq in {chave[0] for chave in self._em_curso}:
            self._zerar(uniq)


def _pista(evento: Evento) -> str:
    """O motor do lado do evento: L2 no esquerdo, R2 no direito, o som do centro nos dois."""
    return _MOTOR_DO_LADO.get(evento.lado, padroes_de_vibracao.AMBOS)


def _valor(passo: int, forca: float) -> int:
    return max(0, min(255, round(passo * forca)))


REACAO_PULSA = "pulsa"
REACAO_EVENTO = "evento"
REACAO_BATIDA = "batida"
TETO_DA_LUZ_POR_S = 3
JANELA_DA_LUZ_S = 1.0
SEGURA_DA_LUZ_S = 0.12
GANHO_MINIMO_DO_PULSO = 1.3
MERGULHO_DO_PULSO = 0.35
COR_DO_EVENTO_PADRAO = (255, 255, 255)
_TIPOS_DA_LUZ = frozenset({TIPO_DEDO, TIPO_RUMBLE})


def pico_do_pulso(base: tuple[int, int, int]) -> tuple[int, int, int] | None:
    """A cor do perfil no brilho máximo; se já está lá, o pulso é um mergulho."""
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
    gatilho E a luz do perfil): a sessão só sai quando o motor solta o último canal
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
        na_economia: Callable[[str], bool] | None = None,
    ) -> None:
        self._pintar = pintar
        self._cor_de = cor_de
        self._devolver = devolver
        self._largar = largar
        self._na_economia = na_economia or (lambda uniq: False)
        self._base: dict[str, tuple[int, int, int]] = {}
        self._no_pico: set[str] = set()
        self._subidas: dict[str, deque[float]] = {}

    @staticmethod
    def _quer(evento: Evento, receita: Receita) -> bool:
        if receita.reacao_ao_tiro == REACAO_BATIDA:
            return evento.tipo == TIPO_BATIDA
        return (
            receita.reacao_ao_tiro in (REACAO_PULSA, REACAO_EVENTO)
            and evento.tipo in _TIPOS_DA_LUZ
        )

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if not self._quer(evento, receita) or evento.uniq in self._no_pico:
            return False
        if self._na_economia(evento.uniq):
            return False
        subidas = self._subidas.setdefault(evento.uniq, deque())
        while subidas and evento.instante - subidas[0] >= JANELA_DA_LUZ_S:
            subidas.popleft()
        if len(subidas) >= TETO_DA_LUZ_POR_S:
            return False
        base = self._cor_de(evento.uniq)
        if base is None or max(base) <= 0:
            self._base.pop(evento.uniq, None)
            return False
        self._base[evento.uniq] = base
        return True

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        uniq = evento.uniq
        base = self._base[uniq]
        if receita.reacao_ao_tiro in (REACAO_PULSA, REACAO_BATIDA):
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
            self._pintar(uniq, base)
            if self._largar is not None:
                self._largar(uniq)


@dataclass(frozen=True)
class Controle:
    """Um controle da mesa como o motor o vê: identidade, pad e os gatilhos."""

    uniq: str
    vpad: Any
    l2: int = 0
    r2: int = 0
    estado_gatilho: tuple[int, int] | None = None
    externo: bool = False
    modo: str | None = None


def _inteiro(valor: Any) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _status_do_disparo(leitor: Any) -> tuple[int, int] | None:
    """O ``(L2, R2)`` do status do Disparo que o leitor do físico viu, ou ``None``.

    Só leitura do que o leitor já tem: nenhuma escrita nova no aparelho, no cabo e no rádio.
    """
    estado = getattr(leitor, "estado_do_gatilho", None)
    if isinstance(estado, tuple) and len(estado) == 2:
        return (_inteiro(estado[0]), _inteiro(estado[1]))
    return None


def controles_do_daemon(daemon: Any) -> list[Controle]:
    """P1 (o pad primário) e P2 a P4 (os jogadores do co-op), cada um com o seu."""
    vistos: dict[str, Controle] = {}
    estilo = estilo_ativo(daemon)
    motor = motor_do(daemon)
    steam_input = motor.steam_input if motor is not None else frozenset()

    def modo_de(vpad: Any) -> str:
        return modo_do_controle(daemon, vpad, estilo=estilo, steam_input=steam_input)

    controller = getattr(daemon, "controller", None)
    primario = getattr(controller, "primary_uniq", None)
    if isinstance(primario, str) and primario:
        estado = getattr(daemon, "_last_state", None)
        vpad_do_primario = getattr(daemon, "_gamepad_device", None)
        vistos[primario] = Controle(
            primario,
            vpad_do_primario,
            _inteiro(getattr(estado, "l2_raw", 0)),
            _inteiro(getattr(estado, "r2_raw", 0)),
            _status_do_disparo(getattr(daemon, "_motion_reader", None)),
            modo=modo_de(vpad_do_primario),
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
            vpad = getattr(jogador, "vpad", None)
            vistos[mac] = Controle(
                mac, vpad, l2, r2,
                _status_do_disparo(getattr(jogador, "motion_reader", None)),
                bool(getattr(jogador, "externo", False)), modo_de(vpad))
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
    controle: Controle, jogo: bool, sessao_ha_s: float | None = None,
    *, motores_no_audio: bool = False,
) -> EstadoDoCanal:
    vpad = controle.vpad
    visto: Mapping[str, float] = {}
    with contextlib.suppress(Exception):
        cru = getattr(vpad, "visto_ha_s", None)
        if isinstance(cru, Mapping):
            visto = cru
    return EstadoDoCanal(
        modo=controle.modo or modo_do_pad(vpad),
        visto_ha_s=visto,
        sessao_aberta=bool(getattr(vpad, "game_open", False)),
        ha_jogo=jogo,
        sessao_ha_s=sessao_ha_s,
        motores_no_audio=motores_no_audio,
    )


def nivel_do_rumble(vpad: Any) -> float:
    """O quanto o jogo pede de rumble a este pad agora, de 0 a 1 (o maior dos dois motores).

    ``ff_last_sent`` é o último par (fraco, forte) entregue ao aparelho, nos dois pads (``uhid`` e
    ``uinput``), e volta a zero quando o jogo para; sem pad ou sem o campo, é zero.
    """
    par = getattr(vpad, "ff_last_sent", None)
    if isinstance(par, tuple) and len(par) == 2 and all(isinstance(x, int) for x in par):
        return float(max(0.0, min(1.0, max(par) / 255.0)))
    return 0.0


def com_o_rumble_anotado(
    estado: EstadoDoCanal, visto_em: float | None, agora: float
) -> EstadoDoCanal:
    """O estado com o rumble que o jogo pediu pelo pad ``uinput`` (o do modo Xbox).

    Só o pad ``uhid`` carimba o ``visto_ha_s``; o rumble do ``uinput`` passa por
    :func:`anotar_o_rumble`. Vale a idade menor das duas, e ``decidir`` cala os motores
    enquanto o jogo vibra, em todo modo.
    """
    if visto_em is None:
        return estado
    carimbo = _CARIMBO_DO_CANAL[CANAL_MOTORES]
    idade = round(max(0.0, agora - visto_em), 1)
    atual = estado.visto_ha_s.get(carimbo)
    if atual is not None and atual <= idade:
        return estado
    return replace(estado, visto_ha_s={**estado.visto_ha_s, carimbo: idade})


_PELO_CARREGADOR: tuple[str, Receita] | None = None
_VISTA_LIDA: tuple[str, Any] | None = None


_VISTA_DO_COMPUTADOR: tuple[Any, Any] | None = None


def _nome_do_perfil_ativo(daemon: Any) -> str:
    """O nome do perfil ativo, ou ``""`` quando não há (o nome que a vista do computador usa)."""
    nome = getattr(getattr(daemon, "store", None), "active_profile", None)
    return nome if isinstance(nome, str) else ""


def _receita_do_computador() -> Receita:
    """Sem perfil ativo, a vista é o computador por baixo de um perfil vazio.

    O mesmo ``perfil_que_vale`` que a aba Vibração usa para mostrar e gravar ali
    (``onde_grava``: sem perfil, grava no computador). O computador que nunca
    escolheu nada dá a vista do perfil vazio, que não escolhe nada: continua desligado.
    """
    global _VISTA_LIDA, _VISTA_DO_COMPUTADOR
    try:
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            o_computador,
            o_perfil_sem_perfil_ativo,
        )

        computador = o_computador()
        feita = _VISTA_DO_COMPUTADOR
        if feita is None or feita[0] is not computador:
            feita = (computador, o_perfil_sem_perfil_ativo(computador))
            _VISTA_DO_COMPUTADOR = feita
        _VISTA_LIDA = ("", feita[1])
        return receita_do_perfil(feita[1])
    except Exception:
        logger.debug("tato_vivo_computador_ilegivel", exc_info=True)
        _VISTA_LIDA = None
        return DESLIGADA


def receita_ativa(daemon: Any) -> Receita:
    """A receita do perfil ativo, lida da vista (o computador por baixo do jogo).

    Sem perfil, vale o computador (:func:`_receita_do_computador`); sem receita,
    desligada. Lê pelo `perfil_em_disco`, que só lê o
    arquivo (sem semear, sem varrer), como o ganho da háptica: este é o laço de
    60 Hz do daemon, e o `load_profile` semeia e reaponta perfis de jogo. Quando o
    nome não tem arquivo com o slug dele, cai no `load_profile` UMA vez por nome
    (A-RECEITA-DO-TATO-SE-LE-SEM-SEMEAR-NEM-VARRER-01). No laço, vale o que o caderno do tique leu.
    """
    nome = _nome_do_perfil_ativo(daemon)
    return cast("Receita", no_caderno(
        daemon, PORTA_DO_TATO, nome, partial(_ler_a_receita, nome),
        periodo_s=RELEITURA_DA_RECEITA_S, vazio=DESLIGADA))


def _ler_a_receita(nome: str) -> Receita:
    """A receita do perfil `nome`, ou a do computador sem nome. Espera o disco."""
    global _PELO_CARREGADOR, _VISTA_LIDA
    if not nome:
        return _receita_do_computador()
    try:
        from hefesto_dualsense4unix.profiles.loader import perfil_em_disco
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        perfil = perfil_em_disco(nome)
        if perfil is not None:
            _PELO_CARREGADOR = None
            vista = o_que_vale(perfil)
            _VISTA_LIDA = (nome, vista)
            return receita_do_perfil(vista)
        if _PELO_CARREGADOR is not None and _PELO_CARREGADOR[0] == nome:
            return _PELO_CARREGADOR[1]
        _PELO_CARREGADOR = (nome, DESLIGADA)
        from hefesto_dualsense4unix.profiles.loader import load_profile

        vista = o_que_vale(load_profile(nome))
        _VISTA_LIDA = (nome, vista)
        receita = receita_do_perfil(vista)
        _PELO_CARREGADOR = (nome, receita)
        return receita
    except Exception:
        logger.debug("tato_vivo_perfil_ilegivel", exc_info=True)
        return DESLIGADA


SECOES_DO_MODO = ("controles", "gatilhos", "luz", "vibracao")
_MODO_DA_ABA_DITO: dict[str, dict[str, Any]] = {}


def extensoes_vivas_do(daemon: Any) -> frozenset[str]:
    """As extensões com a sessão aberta na porta deste serviço."""
    porta = getattr(getattr(daemon, "_mods_supervisor", None), "porta", None)
    vivas = getattr(porta, "vivas", None)
    return frozenset(vivas()) if callable(vivas) else frozenset()


def secoes_do_perfil(perfil: Any, uniq: str | None = None) -> dict[str, str]:
    """O modo de cada seção do perfil, como a aba o pinta; o controle que escreve o seu por
    cima, com o dele."""
    from hefesto_dualsense4unix.profiles.schema import (
        MODO_PERSONALIZADO,
        decidir_o_modo_da_luz,
    )

    lidos = _gatilhos_do_perfil(perfil)
    luz = _ler(perfil, "leds")
    secoes = {
        "controles": _ler(perfil, "controles_modo"),
        "gatilhos": lidos[2] if lidos is not None else None,
        "luz": decidir_o_modo_da_luz(
            _ler(luz, "modo"), _ler(luz, "auto_player_colors") is not False,
            tuple(_ler(luz, "lightbar") or (0, 0, 0)) != (0, 0, 0)) if luz is not None else None,
        "vibracao": _ler(_ler(perfil, "rumble"), "modo"),
    }
    controles = _ler(perfil, "controllers")
    alvo = norm_mac(uniq) if uniq else None
    for chave, dele in (controles.items() if isinstance(controles, Mapping) else ()):
        if alvo and norm_mac(str(chave)) == alvo:
            for secao, campo in (("gatilhos", "triggers"), ("luz", "leds")):
                seu = _ler(_ler(dele, campo), "modo")
                if isinstance(seu, str):
                    secoes[secao] = seu
    return {s: m if isinstance(m, str) else MODO_PERSONALIZADO for s, m in secoes.items()}


def modos_do_perfil_ativo(daemon: Any) -> tuple[str, dict[str, str]]:
    """O nome e as seções do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return nome, {}
    return nome, secoes_do_perfil(lida[1])


def publicar_o_modo_da_aba(daemon: Any, vivas: frozenset[str]) -> None:
    """O ``modo.aba`` de cada controle, só quando muda: a extensão sabe onde o modo pedido vale."""
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import _jogador_de
    from hefesto_dualsense4unix.profiles.schema import modo_que_vale

    bus = getattr(daemon, "bus", None)
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if bus is None or lida is None or lida[0] != nome:
        return
    for controle in controles_do_daemon(daemon):
        secoes = {s: modo_que_vale(m, vivas) or m
                  for s, m in secoes_do_perfil(lida[1], controle.uniq).items()}
        carga = {"uniq": controle.uniq, "jogador": _jogador_de(daemon, controle.uniq),
                 "secoes": secoes}
        if _MODO_DA_ABA_DITO.get(controle.uniq) != carga:
            _MODO_DA_ABA_DITO[controle.uniq] = carga
            bus.publish(EventTopic.MODO_ABA, carga)


def modos_da_aba_ditos() -> list[dict[str, Any]]:
    """O último ``modo.aba`` de cada controle, para quem assina depois."""
    return [dict(c) for c in _MODO_DA_ABA_DITO.values()]


def momentos_ativos(daemon: Any) -> MapaDosMomentos:
    """Os planos dos momentos do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return SEM_MOMENTOS
    try:
        return planos_do_perfil(lida[1], extensoes_vivas_do(daemon))
    except Exception:
        logger.debug("tato_vivo_momentos_ilegiveis", exc_info=True)
        return SEM_MOMENTOS


def escolhas_ativas(daemon: Any) -> dict[str, str]:
    """As formas de toque do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return {}
    try:
        return escolhas_do_perfil(lida[1])
    except Exception:
        logger.debug("tato_vivo_escolhas_ilegiveis", exc_info=True)
        return {}


def escolhas_de_imersao_ativas(daemon: Any) -> dict[str, str]:
    """Os padrões dos motores do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return {}
    try:
        return padroes_do_perfil(lida[1])
    except Exception:
        logger.debug("tato_vivo_padroes_ilegiveis", exc_info=True)
        return {}


def vibracao_do_gatilho_ativa(daemon: Any) -> VibracaoDoGatilho:
    """Onde o gatilho do perfil ativo vibra, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return SEM_VIBRACAO
    try:
        return vibracao_do_gatilho_do_perfil(lida[1], extensoes_vivas_do(daemon))
    except Exception:
        logger.debug("tato_vivo_vibracao_do_gatilho_ilegivel", exc_info=True)
        return SEM_VIBRACAO


def armas_do_gatilho_ativas(daemon: Any) -> ArmasDoGatilho:
    """As armas do ritmo do tiro no perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return SEM_ARMAS
    try:
        return armas_do_gatilho_do_perfil(lida[1], extensoes_vivas_do(daemon))
    except Exception:
        logger.debug("tato_vivo_armas_do_gatilho_ilegiveis", exc_info=True)
        return SEM_ARMAS


def meus_toques_ativos(daemon: Any) -> Any:
    """O ajuste dos meus toques do perfil ativo, da vista que :func:`receita_ativa` leu."""
    from hefesto_dualsense4unix.daemon.subsystems.meus_toques import SEM_TOQUES, ajuste_do_perfil

    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return SEM_TOQUES
    try:
        return ajuste_do_perfil(lida[1])
    except Exception:
        logger.debug("tato_vivo_meus_toques_ilegiveis", exc_info=True)
        return SEM_TOQUES


def estilo_ativo(daemon: Any) -> str | None:
    """A chave do estilo do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return None
    estilo = _ler(lida[1], "estilo")
    return estilo if isinstance(estilo, str) else None


def _controle_na_economia(uniq: str) -> bool:
    """A Bateria longa vale neste controle? (a dele, ou a da mesa quando ele não escolheu)"""
    from hefesto_dualsense4unix.profiles.schema import (
        controles_em_economia,
        economia_da_mesa,
        economia_vale,
    )

    return economia_vale(norm_mac(uniq) in controles_em_economia(), economia_da_mesa())


def _barras_dos_motores(daemon: Any, uniq: str) -> tuple[int, int]:
    """``(forte_pct, fraco_pct)`` das barras dos motores do controle, a pergunta do jogo.

    A mesma de ``gamepad._pcts_dos_motores`` e do «Testar» da aba: no Padrão, 100 e 100.
    """
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    try:
        forte, fraco = gamepad._pcts_dos_motores(daemon, uniq)
        return int(forte), int(fraco)
    except Exception:
        logger.debug("tato_vivo_barras_ilegiveis", exc_info=True)
        return (100, 100)


def _na_forca(valor: int, mult: float) -> int:
    return max(0, min(255, round(valor * mult)))


def _na_barra(valor: int, pontos: int) -> int:
    return _na_forca(valor, pontos / 100.0)


def rota_do_padrao(daemon: Any, uniq: str) -> str:
    """Por onde o padrão do gatilho sai agora; sem quem responda, pelo motor."""
    perguntar = getattr(getattr(daemon, "_alto_falante_subsystem", None), "rota_do_padrao", None)
    return perguntar(uniq) if callable(perguntar) else padroes_de_vibracao.ROTA_MOTOR


def _mults_no_report(daemon: Any, uniq: str) -> tuple[float, float]:
    """``(fraco, forte)`` no report: a Força do controle vezes a barra de cada motor.

    Na economia o padrão já vem na ``FORCA_NA_ECONOMIA``, e o teto da mesa contaria duas vezes.
    """
    forte_pct, fraco_pct = _barras_dos_motores(daemon, uniq)
    degrau = 1.0
    if not _controle_na_economia(uniq):
        from hefesto_dualsense4unix.daemon.subsystems import gamepad

        degrau = gamepad._game_rumble_mult(daemon, time.monotonic(), uniq)
    return degrau * fraco_pct / 100.0, degrau * forte_pct / 100.0


class SaidaDosPadroes:
    """A cadeia de queda, uma só: PCM no tocador, motor pelo report, e o nó do controle de fora.

    O par vem na força do padrão (economia e cena); a Força por controle e as barras são do
    caminho de cada saída. Quem escreveu no motor e mudou de rota zera o motor: o par seguinte
    vai a outro lugar, e o motor ficaria preso no último passo. O zero só vai ao motor que esta
    saída ligou: no Steam Input e no Nativo o report é da Steam ou do jogo.
    """

    def __init__(self, daemon: Any) -> None:
        self._daemon = daemon
        self._do_no: dict[str, tuple[Any, Any]] = {}
        self._no_motor: set[str] = set()

    def _motor_de_fora(self, uniq: str) -> Any:
        jogadores = getattr(getattr(self._daemon, "_coop_manager", None), "_players", None)
        jogador = jogadores.get(uniq) if isinstance(jogadores, dict) else None
        if jogador is None or not getattr(jogador, "externo", False):
            return None
        leitor = getattr(jogador, "reader", None)
        motor, de_quem = self._do_no.get(uniq, (None, None))
        if motor is None or de_quem is not leitor:
            from hefesto_dualsense4unix.core.motor_do_no import MotorDoNo

            motor = MotorDoNo(leitor)
            self._do_no[uniq] = (motor, leitor)
        return motor

    def _vibrar_o_de_fora(self, motor: Any, uniq: str, fraco: int, forte: int) -> object:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import vibrar_o_externo

        return vibrar_o_externo(self._daemon, motor, uniq, fraco, forte) is not None

    def _no_report(self, uniq: str, fraco: int, forte: int) -> object:
        escrever = getattr(getattr(self._daemon, "controller", None), "set_rumble_for", None)
        if not callable(escrever):
            return False
        mult_fraco, mult_forte = _mults_no_report(self._daemon, uniq)
        return escrever(uniq, _na_forca(fraco, mult_fraco), _na_forca(forte, mult_forte))

    def _pelo_motor(self, uniq: str, de_fora: Any, fraco: int, forte: int) -> object:
        if fraco or forte:
            self._no_motor.add(uniq)
        else:
            self._no_motor.discard(uniq)
        if de_fora is not None:
            return self._vibrar_o_de_fora(de_fora, uniq, fraco, forte)
        return self._no_report(uniq, fraco, forte)

    def __call__(self, uniq: str, fraco: int, forte: int) -> object:
        rota = rota_do_padrao(self._daemon, uniq)
        de_fora = self._motor_de_fora(uniq)
        if de_fora is not None and rota == padroes_de_vibracao.ROTA_AUDIO:
            rota = padroes_de_vibracao.ROTA_MOTOR
        if rota != padroes_de_vibracao.ROTA_MOTOR and uniq in self._no_motor:
            self._pelo_motor(uniq, de_fora, 0, 0)
        if rota == padroes_de_vibracao.ROTA_CALADA:
            return False
        if rota == padroes_de_vibracao.ROTA_MOTOR:
            if not fraco and not forte and uniq not in self._no_motor:
                return False
            return self._pelo_motor(uniq, de_fora, fraco, forte)
        forte_pct, fraco_pct = _barras_dos_motores(self._daemon, uniq)
        levar = getattr(
            getattr(self._daemon, "_alto_falante_subsystem", None), "levar_os_lados", None)
        if not callable(levar):
            return False
        return levar(uniq, _na_barra(forte, forte_pct), _na_barra(fraco, fraco_pct))

    def soltar(self, uniq: str) -> None:
        """Zera o motor que esta saída deixou ligado, e só ele."""
        if uniq in self._no_motor:
            self._pelo_motor(uniq, self._motor_de_fora(uniq), 0, 0)

    def largar(self, uniq: str) -> None:
        """O jogo tomou os motores. No nó de fora o efeito do padrão é só dele, e nunca acaba só."""
        de_fora = self._motor_de_fora(uniq)
        if de_fora is not None and uniq in self._no_motor:
            self._vibrar_o_de_fora(de_fora, uniq, 0, 0)
        self._no_motor.discard(uniq)


def saida_dos_padroes(daemon: Any) -> SaidaDosPadroes:
    return SaidaDosPadroes(daemon)


class QuedaDoCorpo:
    """O envelope do grave no par de motores, só enquanto o caminho do áudio não sobe.

    Motor por report não convive com o PCM: a rota saiu do motor, o par zera no mesmo tique. O
    Nativo nunca escreve, e o rumble do jogo passa na frente. A rota é a de todo padrão, então
    Pro e 8BitDo seguem pelo ``EV_FF`` do nó deles, sem ponte e sem prazo.
    """

    def __init__(
        self,
        saida: Any,
        rota_de: Callable[[str], str],
        atrasou: Callable[[str, float], object],
        tem_ponte: Callable[[str], bool] = lambda _uniq: True,
    ) -> None:
        self._saida = saida
        self._rota_de = rota_de
        self._atrasou = atrasou
        self._tem_ponte = tem_ponte
        self._pico: dict[str, float] = {}
        self._ouvido_em: dict[str, float] = {}
        self._desde: dict[str, float] = {}
        self._nivel: dict[str, int] = {}
        self._escrito_em: dict[str, float] = {}
        self._atrasados: set[str] = set()
        self.estados: Mapping[str, str] = MappingProxyType({})

    def ouvir(self, uniq: str, amostras: Any, agora: float) -> None:
        """O grave que este controle devia sentir pelo áudio."""
        pico = max(map(abs, amostras), default=0.0)
        self._pico[uniq] = max(self._pico.get(uniq, 0.0), pico)
        self._ouvido_em[uniq] = agora

    def andar(self, agora: float, estado_de: Callable[[str], EstadoDoCanal | None],
              calados: Collection[str] = ()) -> None:
        """Um tique. ``calados`` são os controles em que um padrão segura os motores agora."""
        for uniq in list(self._ouvido_em):
            self._so_neste(self._andar_um, uniq, agora, estado_de(uniq), uniq in calados)
        estados = {uniq: QUEDA_NO_MOTOR for uniq in self._desde if self._nivel.get(uniq)}
        estados.update(dict.fromkeys(self._atrasados, QUEDA_PASSOU_DO_PRAZO))
        if estados != self.estados:
            self.estados = MappingProxyType(estados)

    def _so_neste(self, passo: Callable[..., object], uniq: str, *resto: object) -> None:
        """A falha de um controle fica nele: os outros da mesa seguem."""
        try:
            passo(uniq, *resto)
        except Exception:
            logger.debug("tato_queda_falhou", exc_info=True)

    def _andar_um(
        self, uniq: str, agora: float, estado: EstadoDoCanal | None, calado: bool
    ) -> None:
        if estado is None or _o_modo_cala_o_motor(estado) or (
                self._rota_de(uniq) != padroes_de_vibracao.ROTA_MOTOR):
            self.soltar(uniq)
            return
        if not decidir(CANAL_MOTORES, estado):
            self._esquecer(uniq)
            self._saida.largar(uniq)
            return
        parado = agora - self._ouvido_em[uniq]
        if calado and parado > SILENCIO_DA_QUEDA_S:
            self._nivel.pop(uniq, None)
            self._saida.largar(uniq)
        if parado > PRAZO_DA_PONTE_S:
            self.soltar(uniq)
            return
        if parado > SILENCIO_DA_QUEDA_S:
            self._zerar(uniq)
            return
        self._ver_o_prazo(uniq, agora)
        if calado or agora - self._escrito_em.get(uniq, float("-inf")) < (
                1.0 / ESCRITAS_DA_QUEDA_POR_S):
            return
        nivel = round(min(1.0, self._pico.pop(uniq, 0.0)) * 255)
        self._escrito_em[uniq] = agora
        if nivel or self._nivel.get(uniq):
            self._nivel[uniq] = nivel
            self._saida(uniq, nivel, nivel)

    def _ver_o_prazo(self, uniq: str, agora: float) -> None:
        desde = self._desde.setdefault(uniq, agora)
        if agora - desde >= PRAZO_DA_PONTE_S and uniq not in self._atrasados and (
                self._tem_ponte(uniq)):
            self._atrasados.add(uniq)
            self._atrasou(uniq, agora - desde)

    def _zerar(self, uniq: str) -> None:
        self._pico.pop(uniq, None)
        if self._nivel.pop(uniq, 0):
            self._saida.soltar(uniq)

    def _esquecer(self, uniq: str) -> None:
        for mapa in (self._ouvido_em, self._desde, self._nivel, self._pico, self._escrito_em):
            mapa.pop(uniq, None)
        self._atrasados.discard(uniq)

    def soltar(self, uniq: str) -> None:
        """A queda sai deste controle: o motor zera, e a ponte volta a ser o regime."""
        self._zerar(uniq)
        self._esquecer(uniq)

    def soltar_tudo(self) -> None:
        for uniq in list(self._ouvido_em):
            self._so_neste(self.soltar, uniq)
        self.estados = MappingProxyType({})


def fator_da_cena(daemon: Any) -> float:
    """O fator da intensidade da cena sobre o que o Hefesto soma; 1,0 sem o motor."""
    motor = motor_do(daemon)
    return 1.0 if motor is None else motor.cena.fator(estilo_ativo(daemon))


def atuadores_de_producao(daemon: Any) -> list[Atuador]:
    """Os canais que o motor sabe escrever hoje."""
    from hefesto_dualsense4unix.daemon.subsystems.chegada import nota_da_unidade

    def ouvindo() -> bool:
        motor = motor_do(daemon)
        return bool(motor is not None and getattr(motor.ouvido, "ouvindo", False))

    def tocar(
        uniq: str, energia: float, lado: str, duracao_ms: int,
        forma: str = formas_de_haptica.TOQUE,
    ) -> object:
        alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
        tocar_o_toque = getattr(alto_falante, "tocar_o_toque", None)
        if not callable(tocar_o_toque):
            return False
        if forma == formas_de_haptica.TOQUE:
            return tocar_o_toque(uniq, energia, lado, duracao_ms)
        return tocar_o_toque(uniq, energia, lado, duracao_ms, forma)

    def escolha_de(uniq: str) -> str | None:
        motor = motor_do(daemon)
        return None if motor is None else motor.escolhas.get(norm_mac(uniq) or "")

    def acordada(uniq: str) -> bool:
        motor = motor_do(daemon)
        return motor is not None and uniq in motor.acordados_pelo_som

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

    def do_momento(uniq: str, lado: str) -> bool:
        motor = motor_do(daemon)
        return motor is not None and motor.momentos.do(uniq, lado) is not None

    def soltar_lado(uniq: str, lado: str, bloco: bytes) -> object:
        soltar = getattr(controller, "soltar_o_gatilho_do_jogo_for", None)
        return soltar(uniq, lado, bloco) if callable(soltar) else False

    def disparo(uniq: str, lado: str) -> int | None:
        motor = motor_do(daemon)
        return None if motor is None else motor.disparo.get((uniq, lado))

    na_economia = _controle_na_economia

    def padrao_de(uniq: str) -> str | None:
        motor = motor_do(daemon)
        escolha = None if motor is None else motor.escolhas_de_imersao.get(norm_mac(uniq) or "")
        return padroes_de_vibracao.padrao_que_vale(escolha, estilo_ativo(daemon))

    def gatilho_vibra(uniq: str) -> bool:
        motor = motor_do(daemon)
        return motor is not None and motor.vibra_o_gatilho.de(uniq)

    def forca_do_padrao(uniq: str) -> float:
        from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

        chave = estilo_ativo(daemon)
        degrau = FORCA_DO_DEGRAU.get(getattr(POR_CHAVE.get(chave or ""), "vibracao", ""), 1.0)
        forca = min(degrau, FORCA_NA_ECONOMIA) if na_economia(uniq) else degrau
        return forca * fator_da_cena(daemon)

    motores = saida_dos_padroes(daemon)

    def momento(uniq: str, lado: str, bloco: bytes) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_DO_MOMENTO)
        return escrever(uniq, lado, bloco)

    def dedo(uniq: str, lado: str, bloco: bytes) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_DO_DEDO)
        return escrever(uniq, lado, bloco)

    from hefesto_dualsense4unix.daemon.subsystems.telemetria_do_jogo import (
        CANAL_DA_TELEMETRIA,
        AtuadorDaTelemetria,
        telemetria_do,
    )

    def gatilho_da_corrida(uniq: str, lado: str, bloco: bytes) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_DA_TELEMETRIA)
        return escrever(uniq, lado, bloco)

    corrida = AtuadorDaTelemetria(
        lambda: telemetria_do(daemon),
        gatilho_da_corrida,
        lambda uniq: sessao.soltar(uniq, CANAL_DA_TELEMETRIA),
        tocar,
        lambda uniq: sessao.largar(uniq, CANAL_DA_TELEMETRIA),
        soltar_lado,
        na_economia=na_economia,
    )

    def a_corrida_quer(uniq: str, lado: str, agora: float) -> bool:
        return corrida.quer_o_lado(uniq, lado, agora)

    def o_lado_tem_dono(uniq: str, lado: str) -> bool:
        return do_momento(uniq, lado) or gatilho_vibra(uniq) or na_economia(uniq)

    def radio_cede(uniq: str) -> bool:
        alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
        chave_de = getattr(alto_falante, "_chave_do_rumble", None)
        cede = getattr(alto_falante, "_o_radio_cede", None)
        if not callable(chave_de) or not callable(cede):
            return False
        chave = chave_de(uniq)
        return chave is not None and bool(cede(chave))

    def arma_de(uniq: str, lado: str) -> bytes | None:
        motor = motor_do(daemon)
        return None if motor is None else motor.armas_do_gatilho.de(uniq, lado)

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
        AtuadorDaHaptica(
            tocar, ouvindo, escolha_de, lambda: estilo_ativo(daemon), na_economia,
            lambda uniq: nota_da_unidade(daemon, uniq), acordada,
            lambda: fator_da_cena(daemon)),
        AtuadorDoSom(estalo),
        AtuadorDoGatilho(
            gatilho,
            lambda uniq: sessao.soltar(uniq, CANAL_GATILHO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_GATILHO),
            do_momento,
            soltar_lado,
            arma_de,
        ),
        AtuadorDosMomentos(
            momento,
            lambda uniq: sessao.soltar(uniq, CANAL_DO_MOMENTO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_DO_MOMENTO),
            na_economia,
            disparo,
            a_corrida_quer,
        ),
        AtuadorDoDedo(
            dedo,
            lambda uniq: sessao.soltar(uniq, CANAL_DO_DEDO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_DO_DEDO),
            o_lado_tem_dono,
            soltar_lado,
            radio_cede,
            arma_de,
        ),
        corrida,
        AtuadorDaLuz(
            pintar,
            cor_de,
            lambda uniq: sessao.soltar(uniq, CANAL_LUZ),
            lambda uniq: sessao.largar(uniq, CANAL_LUZ),
            na_economia,
        ),
        AtuadorDosMotores(
            motores, padrao_de, forca_do_padrao, lambda: estilo_ativo(daemon), motores.largar),
    ]


ORIGEM_DO_JOGO = "jogo"
PREFIXO_DA_EXTENSAO = "extensao:"
VIDA_SEM_PRAZO_S = 3.0
PRAZO_MAXIMO_DE_FORA_S = 300.0
EMPATE_DO_BRILHO = 0.10
TROCA_DA_HAPTICA_S = 0.05
CANAIS_DO_MAIS_NOVO = frozenset({"luz", "leds"})
ESTALOS_GUARDADOS = 16
SOM_DO_RECORTE = "recorte"
JANELA_DO_ESTALO_S = 0.05
TAXA_DE_FORA = 48000
ADIANTE_S = 0.05
GOLPES_POR_PADRAO = 16
DURACAO_MAXIMA_MS = 4000.0
PADROES_POR_EXTENSAO = 32
BPM_DE_FORA = (20.0, 240.0)
_TRES_BITS = frozenset({0x21, 0x26})
_FORCA_NO_BYTE_3 = frozenset({0x22, 0x25})


def o_modo_cala_a_extensao(modo: str | None) -> bool:
    """O modo em que o Hefesto não fala cala a extensão; a falta de jogo, não."""
    return modo is not None and not o_hefesto_fala_no_modo(modo)


def forca_do_bloco(bloco: bytes | bytearray | None) -> int:
    """A força de um bloco de gatilho, de 0 a 8: a maior que o modo aplica em qualquer zona."""
    if not bloco or len(bloco) < 7 or bloco[0] == 0:
        return 0
    modo = bloco[0]
    if modo in _TRES_BITS:
        zonas = bloco[1] | (bloco[2] << 8)
        empacotado = bloco[3] | (bloco[4] << 8) | (bloco[5] << 16) | (bloco[6] << 24)
        if modo == 0x26 and (len(bloco) < 10 or bloco[9] == 0):
            return 0
        return max((((empacotado >> (3 * z)) & 0x07) + 1 for z in range(10)
                    if zonas & (1 << z)), default=0)
    if modo in _FORCA_NO_BYTE_3:
        return (bloco[3] & 0x07) + 1 if bloco[1] | bloco[2] else 0
    maior = max(bloco[1:7])
    return 0 if maior <= 0 else max(1, min(8, round(maior / 255 * 8)))


def brilho_da_luz(rgb: Sequence[Any], brilho: Any = 1.0) -> float:
    """O brilho de uma cor: o maior componente vezes o brilho global, de 0 a 1."""
    try:
        maior = max(float(c) for c in rgb)
        fator = 1.0 if brilho is None else float(brilho)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, maior / 255.0 * max(0.0, min(1.0, fator))))


@dataclass
class PedidoVivo:
    """Um pedido de fora num canal de um controle: de quem, com que força e até quando."""

    origem: str
    forca: float
    em: float
    ate: float
    prazo: bool = False
    coberto: bool = False
    reescrever: Callable[[], object] | None = field(default=None, compare=False)
    ao_vencer: Callable[[], object] | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Veredito:
    """O que o tato vivo responde a uma escrita de fora."""

    vale: bool
    motivo: str = ""
    vence: str | None = None
    fortes: Mapping[str, float] = field(default_factory=dict)
    coberto: bool = False


@dataclass(frozen=True)
class Golpe:
    inicio_ms: float
    dura_ms: float
    frequencia_hz: float
    amplitude: float


@dataclass(frozen=True)
class PadraoDeFora:
    golpes: tuple[Golpe, ...]
    repete: bool

    @property
    def dura_ms(self) -> float:
        return max(g.inicio_ms + g.dura_ms for g in self.golpes)

    @property
    def pico(self) -> float:
        return max(g.amplitude for g in self.golpes)


def padrao_de(dados: Any) -> PadraoDeFora:
    """O padrão registrado: ``{golpes: [[inicio_ms, dura_ms, hz, amplitude]], repete}``."""
    golpes = dados.get("golpes") if isinstance(dados, Mapping) else None
    if not isinstance(golpes, list) or not 1 <= len(golpes) <= GOLPES_POR_PADRAO:
        raise ValueError(f"o padrão pede de 1 a {GOLPES_POR_PADRAO} golpes")
    lidos = []
    for golpe in golpes:
        if not isinstance(golpe, list) or len(golpe) != 4 or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in golpe):
            raise ValueError("cada golpe é [inicio_ms, dura_ms, frequencia_hz, amplitude]")
        inicio, dura, hz, amplitude = (float(v) for v in golpe)
        if (inicio < 0 or not 0 < dura <= DURACAO_MAXIMA_MS or not 1 <= hz <= 1000
                or not 0 <= amplitude <= 1 or inicio + dura > DURACAO_MAXIMA_MS):
            raise ValueError("golpe fora da faixa")
        lidos.append(Golpe(inicio, dura, hz, amplitude))
    return PadraoDeFora(tuple(lidos), bool(dados.get("repete", False)))


def _posicao_ms(padrao: PadraoDeFora, decorrido_ms: float, bpm: float | None) -> float | None:
    if decorrido_ms < 0:
        return None
    if not padrao.repete:
        return decorrido_ms if decorrido_ms < padrao.dura_ms else None
    periodo = 60_000.0 / bpm if bpm else padrao.dura_ms
    return decorrido_ms % max(periodo, 1.0)


def envelope_de(padrao: PadraoDeFora, decorrido_ms: float, bpm: float | None = None) -> float:
    """A amplitude do padrão naquele instante, de 0 a 1: o que o motor imita."""
    posicao = _posicao_ms(padrao, decorrido_ms, bpm)
    if posicao is None:
        return 0.0
    return max((g.amplitude for g in padrao.golpes
                if g.inicio_ms <= posicao < g.inicio_ms + g.dura_ms), default=0.0)


def amostras_de(
    padrao: PadraoDeFora, de_ms: float, quantas: int, forca: float, bpm: float | None = None,
    taxa: int = TAXA_DE_FORA,
) -> array[float]:
    """As amostras do padrão a partir de ``de_ms``: cada golpe é uma senoide que cai."""
    saida = array("f", bytes(4 * max(0, quantas)))
    for i in range(len(saida)):
        posicao = _posicao_ms(padrao, de_ms + i * 1000.0 / taxa, bpm)
        if posicao is None:
            continue
        soma = 0.0
        for golpe in padrao.golpes:
            dentro = posicao - golpe.inicio_ms
            if 0 <= dentro < golpe.dura_ms:
                queda = 1.0 - dentro / golpe.dura_ms
                soma += golpe.amplitude * queda * math.sin(
                    2 * math.pi * golpe.frequencia_hz * dentro / 1000.0)
        saida[i] = max(-1.0, min(1.0, soma * forca))
    return saida


def pcm_do_padrao(padrao: PadraoDeFora, volume: float, taxa: int = TAXA_DE_FORA) -> bytes:
    """O padrão inteiro em s16 estéreo, para o alto-falante."""
    mono = amostras_de(padrao, 0.0, int(taxa * padrao.dura_ms / 1000.0), volume, taxa=taxa)
    estereo = array("h", bytes(4 * len(mono)))
    for i, amostra in enumerate(mono):
        valor = int(amostra * 32767)
        estereo[2 * i] = estereo[2 * i + 1] = valor
    return estereo.tobytes()


@dataclass
class ToqueDeFora:
    origem: str
    padrao: PadraoDeFora
    forca: float
    bpm: float | None
    inicio: float
    ate: float
    pelo_motor: bool
    tocado_ate: float = 0.0
    motor_escrito: float = -1.0


class FonteDeFora:
    """A fonte de fora do tato vivo: as escritas das extensões dividem o teto dele.

    Em cada canal sai o pedido mais forte, do jogo ou de uma extensão, sem soma e sem dono
    fixo; o pedido com prazo fica vivo até ele e volta a sair quando for de novo o mais forte.
    """

    def __init__(
        self,
        teto: Teto,
        *,
        modo_de: Callable[[str], str | None] = lambda uniq: None,
        do_jogo: Callable[[str, str, str], float] = lambda uniq, canal, vaga: 0.0,
        radio_cede: Callable[[str], bool] = lambda uniq: False,
        tocar_haptica: Callable[[str, Any, str], object] = lambda uniq, amostras, lado: False,
        motores: Callable[[str, int, int], object] = lambda uniq, fraco, forte: False,
        tocar_som: Callable[[str, Any], object] = lambda uniq, recorte: False,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.relogio = relogio
        self.teto = teto
        self.modo_de = modo_de
        self.do_jogo = do_jogo
        self.radio_cede = radio_cede
        self.tocar_haptica = tocar_haptica
        self.motores = motores
        self.tocar_som = tocar_som
        self._vivos: dict[tuple[str, str, str], list[PedidoVivo]] = {}
        self._vencedor: dict[tuple[str, str, str], tuple[str, float]] = {}
        self.padroes: dict[tuple[str, str], PadraoDeFora] = {}
        self.sons: dict[tuple[str, str], PadraoDeFora] = {}
        self._devolver: list[tuple[str, str, Callable[[], object]]] = []
        self.toques: dict[tuple[str, str], ToqueDeFora] = {}
        self._estalos: deque[tuple[float, Any]] = deque(maxlen=ESTALOS_GUARDADOS)
        self._trava = threading.Lock()
        self.contadores: dict[str, int] = {
            "pedidos": 0, "escritas": 0, "recusas_do_modo": 0, "recusas_do_teto": 0,
            "mais_fracos": 0, "pelo_motor": 0,
        }

    def _podar(self, chave: tuple[str, str, str], agora: float) -> list[PedidoVivo]:
        vivos = []
        for pedido in self._vivos.get(chave, ()):
            if pedido.ate > agora:
                vivos.append(pedido)
            elif pedido.ao_vencer is not None:
                self._devolver.append((chave[0], chave[1], pedido.ao_vencer))
        if vivos:
            self._vivos[chave] = vivos
        else:
            self._vivos.pop(chave, None)
        return vivos

    def rival(
        self, uniq: str, canal: str, vaga: str, origem: str, agora: float,
    ) -> tuple[str, float, float]:
        """O mais forte do canal fora de ``origem``: ``(origem, força, desde)``."""
        melhor = (ORIGEM_DO_JOGO, float(self.do_jogo(uniq, canal, vaga)), float("-inf"))
        for pedido in self._podar((uniq, canal, vaga), agora):
            if pedido.origem != origem and pedido.forca > melhor[1]:
                melhor = (pedido.origem, pedido.forca, pedido.em)
        return melhor

    def _vence(self, canal: str, forca: float, rival: tuple[str, float, float]) -> bool:
        if canal in CANAIS_DO_MAIS_NOVO and rival[1] > 0:
            return forca >= rival[1] * (1.0 - EMPATE_DO_BRILHO)
        return forca > rival[1]

    def _segura_a_troca(
        self, uniq: str, canal: str, vaga: str, origem: str, agora: float,
    ) -> bool:
        if canal != "haptica":
            return False
        dono = self._vencedor.get((uniq, canal, vaga))
        return dono is not None and dono[0] != origem and agora - dono[1] < TROCA_DA_HAPTICA_S

    def pedir(
        self,
        origem: str,
        canal: str,
        uniq: str,
        vagas: Mapping[str, float],
        agora: float,
        *,
        ate_s: float | None = None,
        reescrever: Callable[[], object] | None = None,
        ao_vencer: Callable[[], object] | None = None,
        vida_s: float = VIDA_SEM_PRAZO_S,
    ) -> Veredito:
        """Uma escrita de fora: o modo, o mais forte em cada vaga e o teto, nesta ordem."""
        self.contadores["pedidos"] += 1
        if o_modo_cala_a_extensao(self.modo_de(uniq)):
            self.contadores["recusas_do_modo"] += 1
            return Veredito(False, "modo", ORIGEM_DO_JOGO)
        prazo = ate_s is not None
        ate = agora + (min(max(ate_s or 0.0, 0.0), PRAZO_MAXIMO_DE_FORA_S) if prazo else vida_s)
        if all(forca <= 0 for forca in vagas.values()):
            self.soltar(origem, canal, uniq, vagas)
            fortes = {v: self.rival(uniq, canal, v, origem, agora)[1] for v in vagas}
            return Veredito(True, "solto", fortes=fortes)
        rivais = {v: self.rival(uniq, canal, v, origem, agora) for v in vagas}
        ganhas = [v for v, forca in vagas.items()
                  if forca > 0 and self._vence(canal, forca, rivais[v])
                  and not self._segura_a_troca(uniq, canal, v, origem, agora)]
        if not ganhas:
            vence = max(rivais.values(), key=lambda r: r[1])[0]
            if not prazo:
                self.contadores["mais_fracos"] += 1
                return Veredito(False, "fraco", vence)
            self._guardar(origem, canal, uniq, vagas, agora, ate, True, reescrever, ao_vencer)
            return Veredito(True, "coberto", vence, coberto=True)
        if not self.teto.cabe(uniq, agora):
            self.contadores["recusas_do_teto"] += 1
            return Veredito(False, "teto")
        self.teto.gastar(uniq, agora)
        self.contadores["escritas"] += 1
        self._guardar(origem, canal, uniq, vagas, agora, ate, prazo, reescrever, ao_vencer)
        for vaga in ganhas:
            self._vencedor[(uniq, canal, vaga)] = (origem, agora)
        fortes = {v: max(forca, rivais[v][1]) for v, forca in vagas.items()}
        return Veredito(True, fortes=fortes)

    def _guardar(
        self, origem: str, canal: str, uniq: str, vagas: Mapping[str, float], agora: float,
        ate: float, prazo: bool, reescrever: Callable[[], object] | None,
        ao_vencer: Callable[[], object] | None = None,
    ) -> None:
        for vaga, forca in vagas.items():
            chave = (uniq, canal, vaga)
            vence = forca > 0 and self._vence(
                canal, forca, self.rival(uniq, canal, vaga, origem, agora))
            vivos = self._podar(chave, agora)
            outros = [p for p in vivos if p.origem != origem]
            herdado = next((p.ao_vencer for p in vivos
                            if p.origem == origem and p.ao_vencer is not None), ao_vencer)
            if forca > 0 and (vence or prazo):
                outros.append(PedidoVivo(origem, forca, agora, ate, prazo, not vence, reescrever,
                                         herdado))
            if outros:
                self._vivos[chave] = outros
            else:
                self._vivos.pop(chave, None)

    def soltar(self, origem: str, canal: str, uniq: str, vagas: Iterable[str]) -> None:
        for vaga in vagas:
            chave = (uniq, canal, vaga)
            outros = [p for p in self._vivos.get(chave, ()) if p.origem != origem]
            self._devolver.extend(
                (uniq, canal, p.ao_vencer) for p in self._vivos.get(chave, ())
                if p.origem == origem and p.ao_vencer is not None)
            if outros:
                self._vivos[chave] = outros
            else:
                self._vivos.pop(chave, None)

    def esquecer(self, origem: str) -> None:
        """A extensão que sai leva os pedidos, os padrões e os toques que eram seus."""
        for chave in list(self._vivos):
            self.soltar(origem, chave[1], chave[0], (chave[2],))
        self.padroes = {k: p for k, p in self.padroes.items() if k[0] != origem}
        self.sons = {k: p for k, p in self.sons.items() if k[0] != origem}
        self.toques = {k: t for k, t in self.toques.items() if t.origem != origem}

    def registrar(self, origem: str, ident: str, padrao: PadraoDeFora) -> None:
        if (origem, ident) not in self.padroes and sum(
                1 for k in self.padroes if k[0] == origem) >= PADROES_POR_EXTENSAO:
            raise ValueError(f"no máximo {PADROES_POR_EXTENSAO} padrões por extensão")
        self.padroes[(origem, ident)] = padrao

    def tocar(
        self, origem: str, uniq: str, lado: str, ident: str, forca: float,
        bpm: float | None, agora: float, ate_s: float | None,
    ) -> Veredito:
        """O padrão registrado na háptica; pelo rádio sem ponte livre, no motor."""
        padrao = self.padroes.get((origem, ident))
        if padrao is None:
            raise ValueError(f"padrão não registrado: {ident}")
        chave = (uniq, lado)
        if forca <= 0 or ate_s == 0:
            atual = self.toques.get(chave)
            if atual is not None and atual.origem == origem:
                del self.toques[chave]
            return self.pedir(origem, "haptica", uniq, {lado: 0.0}, agora)
        prazo = ate_s if ate_s is not None else (
            padrao.dura_ms / 1000.0 if not padrao.repete else VIDA_SEM_PRAZO_S)
        veredito = self.pedir(origem, "haptica", uniq, {lado: forca * padrao.pico}, agora,
                              ate_s=ate_s)
        if not veredito.vale:
            return veredito
        pelo_motor = bool(self.radio_cede(uniq))
        if pelo_motor:
            self.contadores["pelo_motor"] += 1
        self.toques[chave] = ToqueDeFora(origem, padrao, forca, bpm, agora,
                                         agora + min(prazo, PRAZO_MAXIMO_DE_FORA_S), pelo_motor,
                                         tocado_ate=agora)
        self.andar(agora)
        return veredito

    def registrar_som(self, origem: str, ident: str, padrao: PadraoDeFora) -> None:
        if (origem, ident) not in self.sons and sum(
                1 for k in self.sons if k[0] == origem) >= PADROES_POR_EXTENSAO:
            raise ValueError(f"no máximo {PADROES_POR_EXTENSAO} sons por extensão")
        self.sons[(origem, ident)] = padrao

    def som(
        self, origem: str, uniq: str, ident: str, volume: float, agora: float,
        t: float | None = None,
    ) -> Veredito:
        """Um som curto no alto-falante: o da extensão, ou o recorte do estalo do jogo."""
        from hefesto_dualsense4unix.integrations.transiente_do_jogo import recorte_pronto

        padrao = self.sons.get((origem, ident))
        recorte = self.recorte_do(t) if ident == SOM_DO_RECORTE and t is not None else None
        if ident == SOM_DO_RECORTE and recorte is None:
            raise ValueError("nenhum estalo do jogo com esse t")
        if ident != SOM_DO_RECORTE and padrao is None:
            raise ValueError(f"som não registrado: {ident}")
        dura_s = (padrao.dura_ms / 1000.0 if padrao is not None
                  else float(getattr(recorte, "duracao_s", 0.0)))
        if o_modo_cala_a_extensao(self.modo_de(uniq)):
            self.contadores["recusas_do_modo"] += 1
            return Veredito(False, "modo", ORIGEM_DO_JOGO)
        if self.radio_cede(uniq):
            return Veredito(False, "sem_ponte")
        veredito = self.pedir(origem, "som", uniq, {"centro": volume}, agora,
                              vida_s=max(dura_s, JANELA_DO_ESTALO_S))
        if not veredito.vale:
            return veredito
        if padrao is not None and ident != SOM_DO_RECORTE:
            recorte = recorte_pronto(pcm_do_padrao(padrao, volume), agora)
        if not self.tocar_som(uniq, recorte):
            return Veredito(False, "sem_no")
        return veredito

    def guardar_o_estalo(self, estalo: Any) -> None:
        """O estalo que a porta publicou: o recorte dele pode voltar ao alto-falante pelo ``t``."""
        recorte = getattr(estalo, "recorte", None)
        if recorte is not None:
            with self._trava:
                self._estalos.append((float(estalo.instante), recorte))

    def recorte_do(self, t: float) -> Any:
        with self._trava:
            perto = [(abs(instante - t), recorte) for instante, recorte in self._estalos]
        melhor = min(perto, key=lambda par: par[0], default=None)
        return melhor[1] if melhor is not None and melhor[0] <= JANELA_DO_ESTALO_S else None

    def andar(self, agora: float) -> int:
        """O tique: os toques seguem, os prazos vencem e o pedido coberto volta se venceu."""
        escritas = 0
        for chave, toque in list(self.toques.items()):
            uniq, lado = chave
            if agora >= toque.ate:
                del self.toques[chave]
                if toque.pelo_motor:
                    self.motores(uniq, 0, 0)
                continue
            if self._segura_a_troca(uniq, "haptica", lado, toque.origem, agora):
                continue
            escritas += self._levar(uniq, lado, toque, agora)
        for vivo in list(self._vivos):
            for pedido in self._podar(vivo, agora):
                if not pedido.coberto or pedido.reescrever is None:
                    continue
                rival = self.rival(vivo[0], vivo[1], vivo[2], pedido.origem, agora)
                if self._vence(vivo[1], pedido.forca, rival) and self.teto.cabe(vivo[0], agora):
                    self.teto.gastar(vivo[0], agora)
                    pedido.coberto = False
                    pedido.reescrever()
                    escritas += 1
        return escritas + self._devolver_o_que_venceu()

    def _devolver_o_que_venceu(self) -> int:
        pendentes, self._devolver = self._devolver, []
        feitas = 0
        for uniq, canal, devolver in pendentes:
            if any(c[0] == uniq and c[1] == canal for c in self._vivos):
                continue
            try:
                devolver()
            except Exception:
                logger.warning("tato_de_fora_nao_devolveu", uniq=uniq, canal=canal, exc_info=True)
                continue
            feitas += 1
        return feitas

    def _levar(self, uniq: str, lado: str, toque: ToqueDeFora, agora: float) -> int:
        decorrido_ms = (agora - toque.inicio) * 1000.0
        if toque.pelo_motor:
            nivel = round(255 * toque.forca * envelope_de(toque.padrao, decorrido_ms, toque.bpm))
            if nivel == toque.motor_escrito:
                return 0
            toque.motor_escrito = nivel
            forte, fraco = (nivel, 0) if lado == LADO_ESQUERDO else (0, nivel)
            self.motores(uniq, fraco, forte)
            return 1
        ate = min(agora + ADIANTE_S, toque.ate)
        quantas = int((ate - toque.tocado_ate) * TAXA_DE_FORA)
        if quantas <= 0:
            return 0
        de_ms = (toque.tocado_ate - toque.inicio) * 1000.0
        amostras = amostras_de(toque.padrao, de_ms, quantas, toque.forca, toque.bpm)
        toque.tocado_ate += quantas / TAXA_DE_FORA
        self.tocar_haptica(uniq, amostras, lado)
        return 1


def _do_jogo_de_producao(daemon: Any) -> Callable[[str, str, str], float]:
    from hefesto_dualsense4unix.core.trigger_effects import bloco_do_efeito
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import par_nos_motores

    def saida_do_jogo(uniq: str) -> Any:
        pintado = getattr(getattr(daemon, "controller", None), "_game_output_by_uniq", None)
        alvo = norm_mac(uniq)
        if not isinstance(pintado, dict) or alvo is None:
            return None
        return next((v for k, v in pintado.items() if norm_mac(k) == alvo), None)

    def do_jogo(uniq: str, canal: str, vaga: str) -> float:
        if canal == "vibracao":
            fraco, forte = par_nos_motores(daemon, uniq)
            return (forte if vaga == LADO_ESQUERDO else fraco) / 255.0
        if canal == "luz":
            led = getattr(saida_do_jogo(uniq), "led", None)
            return brilho_da_luz(led) if led is not None else 0.0
        if canal == "gatilho":
            blocos = getattr(getattr(daemon, "controller", None), "_game_triggers_by_uniq", None)
            alvo = norm_mac(uniq)
            lado = "left" if vaga == LADO_ESQUERDO else "right"
            do_controle = next((v for k, v in blocos.items() if norm_mac(k) == alvo), None) if (
                isinstance(blocos, dict) and alvo is not None) else None
            bloco = do_controle.get(lado) if isinstance(do_controle, dict) else None
            if bloco is None:
                efeito = getattr(saida_do_jogo(uniq), f"trigger_{lado}", None)
                bloco = bloco_do_efeito(efeito) if efeito is not None else None
            return forca_do_bloco(bloco) / 8.0
        if canal == "haptica":
            entradas = getattr(daemon, "_envelopes_da_haptica_vistos", None)
            alvo = norm_mac(uniq)
            entrada = next((v for k, v in entradas.items() if norm_mac(k) == alvo), None) if (
                isinstance(entradas, dict) and alvo is not None) else None
            nivel = getattr(getattr(entrada, "envelope", None), "ultimo", None)  # (noqa-acento)
            if not nivel:
                return 0.0
            return float(nivel[0] if vaga == LADO_ESQUERDO else nivel[1])
        return 0.0

    return do_jogo


def ligar_a_fonte_de_fora(daemon: Any, fonte: FonteDeFora) -> FonteDeFora:
    """A fonte de fora com os olhos e as mãos do daemon: o modo, o jogo, o rádio e as saídas."""

    def modo_de(uniq: str) -> str | None:
        alvo = norm_mac(uniq)
        controle = next((c for c in controles_do_daemon(daemon) if norm_mac(c.uniq) == alvo), None)
        if controle is None:
            return None
        return controle.modo or modo_do_pad(controle.vpad)

    def falante() -> Any:
        return getattr(daemon, "_alto_falante_subsystem", None)

    def radio_cede(uniq: str) -> bool:
        quem = falante()
        chave = quem._chave_do_rumble(uniq) if quem is not None else None
        if quem is None or chave is None:
            return False
        return bool(quem._o_radio_cede(chave))

    def tocar_haptica(uniq: str, amostras: Any, lado: str) -> bool:
        quem = falante()
        return bool(quem is not None and quem.tocar_o_corpo(uniq, amostras, lado))

    def motores(uniq: str, fraco: int, forte: int) -> bool:
        quem = falante()
        pelo_audio = getattr(quem, "a_vibracao_vai_pelo_audio_em", None)
        levar = getattr(quem, "levar_o_rumble", None)
        if callable(levar):
            converte = callable(pelo_audio) and pelo_audio(uniq) is True
            leva = levar(uniq, fraco if converte else 0, forte if converte else 0)
            if converte:
                return leva is True
        controle = getattr(daemon, "controller", None)
        escrever = getattr(controle, "set_rumble_for", None)
        return bool(callable(escrever) and escrever(uniq, fraco, forte))

    def tocar_som(uniq: str, recorte: Any) -> bool:
        quem = falante()
        return bool(quem is not None and quem.tocar_o_estalo(uniq, recorte))

    fonte.modo_de = modo_de
    fonte.do_jogo = _do_jogo_de_producao(daemon)
    fonte.radio_cede = radio_cede
    fonte.tocar_haptica = tocar_haptica
    fonte.motores = motores
    fonte.tocar_som = tocar_som
    return fonte


def _o_que_cala_o_corpo(uniq: str, estado: EstadoDoCanal) -> str | None:
    """Por que quem escolheu o corpo não recebe; o modo que cala não é recusa: nada toca ali."""
    if _o_modo_cala_o_motor(estado):
        return None
    if not decidir(CANAL_HAPTICA, estado):
        return RECUSA_JOGO_NO_ENDPOINT
    return RECUSA_ECONOMIA if _controle_na_economia(uniq) else None


def cor_do_plastico_de(daemon: Any, uniq: str) -> str | None:
    """O nome da cor do plástico de ``uniq``; ``None`` quando a fábrica ainda não disse."""
    ler = getattr(getattr(daemon, "identity_registry", None), "identidade_de_fabrica", None)
    if not callable(ler):
        return None
    return getattr(getattr(ler(uniq), "cor", None), "nome", None) or None


def subida_ao_store(daemon: Any) -> Callable[[str, int], object]:
    """Quem leva a conta do minuto ao ``store``; sem ``store``, nada sobe."""
    subir = getattr(getattr(daemon, "store", None), "bump", None)
    return subir if callable(subir) else lambda _chave, _delta: None


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
        self._vivas: frozenset[str] = frozenset()
        self._aberta_em: dict[str, float | None] = {}
        self._filtro_do_corpo = formas_de_haptica.FiltroDoCorpo()
        self._corpo: deque[Any] = deque(maxlen=CORPO_MAX_PEDACOS)
        self._tetos_do_corpo: dict[str, formas_de_haptica.TetoDoCorpo] = {}
        self._graos: dict[str, formas_de_haptica.GeradorDoGrao] = {}
        self._motores_de_epoca: dict[str, formas_de_haptica.GeradorDoMotorDeEpoca] = {}
        self._continua_em: dict[str, float] = {}
        self._agora_da_continua = 0.0
        self.fonte_do_som = FonteDoSom()
        self._corpo_discreto: frozenset[str] = frozenset()
        self._externos: frozenset[str] = frozenset()
        self.diario_do_corpo = DiarioDoCorpo(
            lambda uniq: cor_do_plastico_de(daemon, uniq), subida_ao_store(daemon))
        self.queda_do_corpo = motor.queda = QuedaDoCorpo(
            saida_dos_padroes(daemon), lambda uniq: rota_do_padrao(daemon, uniq),
            self._a_ponte_atrasou, self._pede_ponte)

    def _pede_ponte(self, uniq: str) -> bool:
        """Pro e 8BitDo não têm voice-coil: neles o motor é o regime."""
        return uniq not in self._externos

    def _a_ponte_atrasou(self, uniq: str, ha_s: float) -> None:
        """O regime é a ponte de pé: passou do prazo, o diário diz com o motivo do dono."""
        por_que = getattr(
            getattr(self.daemon, "_alto_falante_subsystem", None), "por_que_sem_ponte", None)
        logger.warning(
            "tato_corpo_pelo_motor_passou_do_prazo", controle=self.diario_do_corpo.rotulo(uniq),
            ha_s=round(ha_s), motivo=por_que(uniq) if callable(por_que) else None)

    def som_assinado(self) -> bool:
        """Uma extensão assina o som do jogo pela porta."""
        return tem_assinante(getattr(self.daemon, "bus", None), EventTopic.JOGO_SOM)

    def _o_tato_quer_o_som(self) -> bool:
        return self.motor.ligado and pede_o_ouvido(self.receita_vigente)

    def _som_so_da_porta(self) -> bool:
        return not self._o_tato_quer_o_som() and self.som_assinado()

    def ouvido_quer(self) -> bool:
        """O ouvido grava com jogo em cena quando o tato vivo pede o som ou a porta o assina."""
        return (self._o_tato_quer_o_som() or self.som_assinado()) and self.jogo

    def _som_para_a_porta(self) -> None:
        if not self.som_assinado():
            return
        self.jogo = ha_jogo(self.daemon)
        ouvido = self.motor.ouvido
        if ouvido is not None:
            ouvido.comecar()
            ouvido.tirar()

    def receita_de_agora(self, agora: float) -> Receita:
        vivas = extensoes_vivas_do(self.daemon)
        relida = agora - self._lida_em >= RELEITURA_DA_RECEITA_S or vivas != self._vivas
        if a_resposta_chegou(self.daemon, PORTA_DO_TATO) or relida:
            self._lida_em = agora
            self._vivas = vivas
            self.receita_vigente = receita_ativa(self.daemon)
            publicar_o_modo_da_aba(self.daemon, vivas)
            self.motor.momentos = (
                momentos_ativos(self.daemon)
                if self.receita_vigente.momentos_da_imersao else SEM_MOMENTOS)
            self.motor.escolhas = escolhas_ativas(self.daemon)
            self.motor.escolhas_de_imersao = escolhas_de_imersao_ativas(self.daemon)
            self.motor.vibra_o_gatilho = vibracao_do_gatilho_ativa(self.daemon)
            self.motor.armas_do_gatilho = armas_do_gatilho_ativas(self.daemon)
            if self.motor.meus_toques is not None:
                self.motor.meus_toques.ajustar(meus_toques_ativos(self.daemon))
        return self.receita_vigente

    def alimentar_o_corpo(self, pcm: bytes) -> None:
        """Chamado na thread do ouvido: o PCM do jogo vira o grave, se alguém o quer, e a energia
        do som vai à intensidade da cena."""
        self.diario_do_corpo.somar_o_pcm(len(pcm))
        if self._som_so_da_porta():
            return
        self.motor.cena.ouvir_o_som(pcm)
        if self.receita_vigente.som_no_corpo_escolhido or self._corpo_discreto:
            pedaco = self._filtro_do_corpo.processar(pcm)
            self._corpo.append((pedaco, max(map(abs, pedaco), default=0.0) >= SINAL_DO_CORPO))

    def _levar_o_corpo(
        self, receita: Receita, uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
    ) -> None:
        """O grave do jogo vai a cada controle que escolheu o Som no corpo e onde o jogo cala."""
        pedacos = []
        while self._corpo:
            try:
                pedacos.append(self._corpo.popleft())
            except IndexError:
                break
        if not pedacos:
            return
        com_sinal = any(sinal for _pedaco, sinal in pedacos)
        donos = []
        for uniq in uniqs if receita.som_no_corpo_escolhido else ():
            estado = estado_de(uniq)
            forma = formas_de_haptica.forma_que_vale(
                self.motor.escolhas.get(norm_mac(uniq) or ""), estilo_ativo(self.daemon))
            if forma != formas_de_haptica.SOM_NO_CORPO or estado is None:
                continue
            motivo = _o_que_cala_o_corpo(uniq, estado)
            if motivo is None and not _o_modo_cala_o_motor(estado):
                donos.append(uniq)
            elif motivo is not None:
                self._recusar(uniq, motivo)
        discretos = [u for u in uniqs if u in self._corpo_discreto and u not in donos]
        if not donos and not discretos:
            return
        amostras = array("f")
        for pedaco, _sinal in pedacos:
            amostras.extend(pedaco)
        alto_falante = getattr(self.daemon, "_alto_falante_subsystem", None)
        levar = getattr(alto_falante, "tocar_o_corpo", None)
        if not callable(levar):
            for uniq in (*donos, *discretos):
                self._recusar(uniq, RECUSA_SEM_APARELHO)
            return
        fator = fator_da_cena(self.daemon)
        tocam = {*donos, *discretos}
        self._tetos_do_corpo = {u: t for u, t in self._tetos_do_corpo.items() if u in tocam}
        for uniq in donos:
            meu = self._sob_o_teto(uniq, amostras, fator)
            self._cair_pelo_motor(
                uniq, meu, self._entregar(levar, uniq, meu, com_sinal), com_sinal)
        for uniq in discretos:
            metade = self._sob_o_teto(uniq, amostras, fator * FORCA_DO_CORPO_DISCRETO)
            self._cair_pelo_motor(
                uniq, metade, self._entregar(levar, uniq, metade, com_sinal), com_sinal)

    def _sob_o_teto(self, uniq: str, amostras: Any, forca: float) -> Any:
        """O corpo de ``uniq`` sob o teto do ganho dele, na ``forca`` da cena: o susto sai a 70%
        do pico de hoje e solta devagar."""
        teto = self._tetos_do_corpo.setdefault(uniq, formas_de_haptica.TetoDoCorpo())
        teto.teto = formas_de_haptica.teto_do_susto(GANHO.fator(uniq))
        meu = teto.passar(amostras)
        return meu if forca == 1.0 else array("f", [x * forca for x in meu])

    def _cair_pelo_motor(self, uniq: str, amostras: Any, desfecho: Any, com_sinal: bool) -> None:
        """O tocador segue acordando a ponte; a queda ouve quem pode sentir pelo motor."""
        if com_sinal and getattr(desfecho, "motivo", None) not in RECUSAS_SEM_QUEDA:
            self.queda_do_corpo.ouvir(uniq, amostras, self._agora_da_continua)

    def _ler_a_lista_do_steam_input(self) -> None:
        """A lista só importa com o Modo Nativo ligado, e o disco fica fora do tique."""
        nativo = getattr(self.daemon, "is_native_mode", None)
        if not callable(nativo) or not nativo():
            return
        from hefesto_dualsense4unix.daemon.launch_env import steam_input_appids

        self.motor.steam_input = frozenset(steam_input_appids())

    def _recusar(self, uniq: str, motivo: str) -> None:
        """Pro e 8BitDo não têm voice-coil: ali nada toca, e isso não é recusa."""
        if uniq not in self._externos:
            self.diario_do_corpo.recusado(uniq, motivo)

    def _entregar(
        self, levar: Callable[..., Any], uniq: str, amostras: Any, com_sinal: bool
    ) -> Any:
        desfecho = levar(uniq, amostras)
        if not desfecho:
            self._recusar(uniq, getattr(desfecho, "motivo", None) or RECUSA_SEM_APARELHO)
        elif com_sinal:
            self.diario_do_corpo.entregue(uniq)
        return desfecho

    def andar_o_diario(self, agora: float) -> None:
        """O passo do diário do corpo, chamado fora do tique: a falha fica neste passo."""
        try:
            self._ler_a_lista_do_steam_input()
            ouvido = self.motor.ouvido
            self.diario_do_corpo.andar(
                agora, jogo=self.jogo, pedido=self.ouvido_quer(),
                surdo_ha_s=ouvido.surdo_ha_s() if ouvido is not None else 0.0)
        except Exception:
            logger.debug("tato_diario_do_corpo_falhou", exc_info=True)

    def _acordar_a_fonte_do_som(
        self, receita: Receita, controles: Sequence[Controle], jogo: bool,
        estado_de: Callable[[str], EstadoDoCanal | None], agora: float,
    ) -> None:
        """Onde o jogo cala e a pessoa joga, o som do jogo acorda; o rumble o cala no tique."""
        if not receita.som_quando_o_jogo_cala:
            self.motor.acordados_pelo_som = self._corpo_discreto = frozenset()
            return
        from hefesto_dualsense4unix.daemon.subsystems.meus_toques import entradas_do_daemon

        entradas = {e.uniq: e for e in entradas_do_daemon(self.daemon)}
        acordados = set()
        for c in controles:
            estado = estado_de(c.uniq)
            calado_aqui = self.fonte_do_som.ver(
                c.uniq, agora, jogo=jogo, vpad=c.vpad,
                rumble_em=self.motor.rumble_com_forca_em.get(norm_mac(c.uniq) or c.uniq),
                entrada=entradas.get(c.uniq))
            if calado_aqui and estado is not None and decidir(CANAL_HAPTICA, estado):
                acordados.add(c.uniq)
        estilo = estilo_ativo(self.daemon)
        corpo = estilo in ESTILOS_DO_CORPO_DISCRETO
        self.motor.acordados_pelo_som = frozenset(acordados)
        self._corpo_discreto = frozenset(
            u for u in acordados if corpo and not _controle_na_economia(u))

    def _donos_da_continua(
        self, chave: str, uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
    ) -> list[str]:
        """Os controles onde esta forma contínua toca agora: o jogo cala o canal, sem economia."""
        donos = []
        for uniq in uniqs:
            estado = estado_de(uniq)
            forma = formas_de_haptica.forma_que_vale(
                self.motor.escolhas.get(norm_mac(uniq) or ""), estilo_ativo(self.daemon))
            if (forma == chave and estado is not None and decidir(CANAL_HAPTICA, estado)
                    and not _controle_na_economia(uniq)):
                donos.append(uniq)
        return donos

    def _amostras_devidas(self, chave: str, agora: float) -> int:
        """Quantas amostras cabem desde o último pedaço desta forma (no máximo um décimo de s)."""
        antes = self._continua_em.get(chave)
        self._continua_em[chave] = agora
        decorrido = INTERVALO_S if antes is None else max(0.0, min(0.1, agora - antes))
        return round(formas_de_haptica.TAXA * decorrido)

    def _levar_a_continua(self, uniq: str, amostras: Any) -> None:
        alto_falante = getattr(self.daemon, "_alto_falante_subsystem", None)
        levar = getattr(alto_falante, "tocar_o_corpo", None)
        if callable(levar) and len(amostras):
            self._entregar(levar, uniq, amostras, True)

    def _levar_o_grao(
        self, receita: Receita, uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
    ) -> None:
        """Os grãos finos e rápidos, sem parar, onde o controle tem o Grão e o jogo cala o canal."""
        donos = (self._donos_da_continua(formas_de_haptica.GRAO, uniqs, estado_de)
                 if receita.grao_escolhido else [])
        for uniq in [u for u in self._graos if u not in donos]:
            del self._graos[uniq]
        if not donos:
            self._continua_em.pop(formas_de_haptica.GRAO, None)
            return
        n = self._amostras_devidas(formas_de_haptica.GRAO, self._agora_da_continua)
        for uniq in donos:
            gerador = self._graos.setdefault(uniq, formas_de_haptica.GeradorDoGrao())
            self._levar_a_continua(uniq, gerador.gerar(n))

    def _levar_o_motor_de_epoca(
        self, receita: Receita, uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        vpad_de: Callable[[str], Any],
    ) -> None:
        """O zumbido que sobe e arrasta com o rumble do jogo; sem rumble, mudo."""
        donos = (self._donos_da_continua(formas_de_haptica.MOTOR_DE_EPOCA, uniqs, estado_de)
                 if receita.motor_de_epoca_escolhido else [])
        for uniq in [u for u in self._motores_de_epoca if u not in donos]:
            del self._motores_de_epoca[uniq]
        if not donos:
            self._continua_em.pop(formas_de_haptica.MOTOR_DE_EPOCA, None)
            return
        n = self._amostras_devidas(formas_de_haptica.MOTOR_DE_EPOCA, self._agora_da_continua)
        for uniq in donos:
            gerador = self._motores_de_epoca.get(uniq)
            nivel = nivel_do_rumble(vpad_de(uniq))
            if gerador is None:
                if nivel <= 0.0:
                    continue
                gerador = self._motores_de_epoca[uniq] = formas_de_haptica.GeradorDoMotorDeEpoca()
            elif nivel <= 0.0 and gerador.calado:
                del self._motores_de_epoca[uniq]
                continue
            self._levar_a_continua(uniq, gerador.gerar(n, nivel))

    def __call__(self, agora: float) -> int:
        """A volta dos acessórios e os meus toques andam a cada tique; o resto é da receita."""
        volta = self.motor.volta
        da_volta = volta.tique(agora) if volta is not None else 0
        da_receita = self._da_receita(agora)
        return da_receita + da_volta + self._meus_toques(agora)

    def _meus_toques(self, agora: float) -> int:
        """Os meus toques de cada controle da mesa; sem o bloco no perfil, nada se monta."""
        meus = self.motor.meus_toques
        if meus is None or not meus.precisa_andar():
            return 0
        from hefesto_dualsense4unix.daemon.subsystems.meus_toques import entradas_do_daemon

        return int(meus.tique(entradas_do_daemon(self.daemon), agora))

    def _da_receita(self, agora: float) -> int:
        receita = self.receita_de_agora(agora)
        ligado = receita.ligada
        if not ligado:
            if self.motor.ligado:
                self.motor.parar(agora)
            self.motor.ligado = False
            self._aberta_em.clear()
            self.motor.acordados_pelo_som = self._corpo_discreto = frozenset()
            self.motor.cena.esquecer()
            self._som_para_a_porta()
            return 0
        self.motor.ligado = True
        controles = controles_do_daemon(self.daemon)
        self._externos = frozenset(c.uniq for c in controles if c.externo)
        for controle in controles:
            for evento in self.dedo.ver(controle.uniq, controle.l2, controle.r2, agora):
                self.motor.anotar(evento)
            self._anotar_o_disparo(controle)
        for solta in self.dedo.tirar_as_soltas():
            self.motor.anotar(solta)
        self._ouvir_o_jogo(receita, controles)
        jogo = self.jogo = ha_jogo(self.daemon)
        por_uniq = {
            c.uniq: com_o_rumble_anotado(
                estado_do_controle(
                    c, jogo, self._sessao_ha_s(c, agora), motores_no_audio=(
                        rota_do_padrao(self.daemon, c.uniq) == padroes_de_vibracao.ROTA_AUDIO)),
                self.motor.rumble_visto_em.get(norm_mac(c.uniq) or c.uniq),
                agora,
            )
            for c in controles
        }
        self._acordar_a_fonte_do_som(receita, controles, jogo, por_uniq.get, agora)
        escritas = self.motor.tique(agora, por_uniq.get, receita, uniqs=tuple(por_uniq))
        self.motor.cena.andar(
            agora, jogo=jogo,
            ouvido=bool(getattr(self.motor.ouvido, "ouvindo", False))
            and not self._som_so_da_porta(),
            uniqs=tuple(por_uniq))
        self._agora_da_continua = agora
        self._levar_o_corpo(receita, tuple(por_uniq), por_uniq.get)
        self.queda_do_corpo.andar(agora, por_uniq.get, self.motor.segurando(CANAL_MOTORES))
        vpads = {c.uniq: c.vpad for c in controles}
        self._levar_o_grao(receita, tuple(por_uniq), por_uniq.get)
        self._levar_o_motor_de_epoca(receita, tuple(por_uniq), por_uniq.get, vpads.get)
        return escritas

    def _anotar_o_disparo(self, controle: Controle) -> None:
        """O status do Disparo de cada lado vai ao motor; sem report, o lado não tem status."""
        for lado, valor in zip(
                (LADO_ESQUERDO, LADO_DIREITO), controle.estado_gatilho or (None, None),
                strict=True):
            if valor is None:
                self.motor.disparo.pop((controle.uniq, lado), None)
            else:
                self.motor.disparo[(controle.uniq, lado)] = valor

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
        if pede_o_ouvido(receita) or self.som_assinado():
            ouvido.comecar()
        batida = receita.reacao_ao_tiro == REACAO_BATIDA
        estalos = ouvido.tirar()
        if not pede_o_ouvido(receita) and self.som_assinado():
            return
        for estalo in estalos:
            for uniq in destinos_do_som(controles, self.dedo, estalo.instante):
                self.motor.anotar(
                    Evento(estalo.instante, uniq, TIPO_SOM, estalo.lado, estalo.energia,
                           getattr(estalo, "recorte", None))
                )
            for controle in controles if batida else ():
                self.motor.anotar(
                    Evento(estalo.instante, controle.uniq, TIPO_BATIDA, estalo.lado,
                           estalo.energia))


async def _diario_do_corpo_loop(daemon: DaemonProtocol, passo: Passo) -> None:
    """A linha do minuto, fora do tique: quem escreve no diário não segura o laço de 60 Hz."""
    while not daemon._is_stopping():
        await asyncio.sleep(PASSO_DO_DIARIO_S)
        await asyncio.to_thread(passo.andar_o_diario, time.monotonic())


async def tato_vivo_loop(daemon: DaemonProtocol, motor: TatoVivo) -> None:
    passo = Passo(daemon, motor)
    if motor.ouvido is None:
        from hefesto_dualsense4unix.integrations.transiente_do_jogo import OuvidoDoJogo

        barramento_do_som = getattr(daemon, "bus", None)
        motor.ouvido = OuvidoDoJogo(
            passo.ouvido_quer,
            recortar=lambda: passo.receita_vigente.som_no_controle or passo.som_assinado(),
            ao_pcm=passo.alimentar_o_corpo,
            publicar=(
                None if barramento_do_som is None
                else lambda carga: barramento_do_som.publish(EventTopic.JOGO_SOM, carga)),
            assinado=passo.som_assinado,
            ao_estalo=motor.de_fora.guardar_o_estalo,
        )
    diario = asyncio.create_task(
        _diario_do_corpo_loop(daemon, passo), name="tato_diario_do_corpo")
    volta = motor.volta
    barramento = getattr(daemon, "bus", None) if volta is not None else None
    gestos = estados = None
    if barramento is not None:
        gestos = barramento.subscribe(EventTopic.ACESSORIOS_GESTO)
        estados = barramento.subscribe(EventTopic.ACESSORIOS_ESTADO)
    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_S)
            agora = time.monotonic()
            if gestos is not None and estados is not None:
                volta.drenar(gestos, estados, agora)
            passo.tique_do_laco(agora)
            motor.de_fora.andar(agora)
    finally:
        diario.cancel()
        if barramento is not None:
            barramento.unsubscribe(EventTopic.ACESSORIOS_GESTO, gestos)
            barramento.unsubscribe(EventTopic.ACESSORIOS_ESTADO, estados)
        for quem in (volta, motor.meus_toques):
            try:
                if quem is not None:
                    quem.soltar_tudo(time.monotonic())
            except Exception:
                logger.warning("tato_vivo_toque_nao_soltou", exc_info=True)
        motor.parar()
        with contextlib.suppress(Exception):
            await asyncio.to_thread(motor.ouvido.parar)


def start_tato_vivo(daemon: DaemonProtocol) -> None:
    """Sobe o motor do tato vivo. Desligado pela receita, o laço só lê o perfil."""
    from hefesto_dualsense4unix.daemon.subsystems.meus_toques import meus_toques_de_producao
    from hefesto_dualsense4unix.daemon.subsystems.volta_dos_acessorios import volta_de_producao

    motor = TatoVivo(atuadores_de_producao(daemon))
    ligar_a_fonte_de_fora(daemon, motor.de_fora)
    try:
        motor.volta = volta_de_producao(daemon)
    except Exception:
        logger.warning("tato_vivo_sem_a_volta_dos_acessorios", exc_info=True)
    motor.meus_toques = meus_toques_de_producao(daemon)
    daemon._meus_toques = motor.meus_toques  # type: ignore[attr-defined]
    daemon._tato_vivo = motor  # type: ignore[attr-defined]
    task = asyncio.create_task(tato_vivo_loop(daemon, motor), name="tato_vivo_loop")
    daemon._tasks.append(task)
    logger.info("tato_vivo_iniciado")


__all__ = [
    "CAMPOS_DA_RECEITA",
    "CAMPO_DA_RECEITA",
    "CANAIS",
    "CANAL_DO_DEDO",
    "DEGRAUS_DO_DEDO",
    "DESLIGADA",
    "ENTRADA_VIVA_S",
    "ESTILOS_DE_GOLPE",
    "ESTILOS_DO_CORPO_DISCRETO",
    "FORCA_DO_CORPO_DISCRETO",
    "FREQUENCIA_DO_DEDO_HZ",
    "HISTERESE_DO_DEDO",
    "MODO_DUALSENSE",
    "MODO_NATIVO",
    "MODO_XBOX",
    "SEM_RUMBLE_NO_DEDO_S",
    "SEM_RUMBLE_S",
    "Atuador",
    "AtuadorDaHaptica",
    "AtuadorDaLuz",
    "AtuadorDoDedo",
    "AtuadorDoGatilho",
    "AtuadorDoSom",
    "AtuadorDosMomentos",
    "AtuadorDosMotores",
    "BordaDoDedo",
    "BordaDoRumble",
    "Controle",
    "EstadoDoCanal",
    "Evento",
    "FonteDeFora",
    "FonteDoSom",
    "MapaDosMomentos",
    "PadraoDeFora",
    "Passo",
    "PedidoVivo",
    "PlanoDoGatilho",
    "Receita",
    "SessaoDoMotor",
    "TatoVivo",
    "Teto",
    "Veredito",
    "VibracaoDoGatilho",
    "anotar_o_rumble",
    "bloco_do_dedo",
    "bloco_do_gatilho",
    "brilho_da_luz",
    "controles_do_daemon",
    "decidir",
    "degrau_do_rumble",
    "destinos_do_som",
    "duracao_do_toque_do_estilo",
    "escolhas_ativas",
    "escolhas_de_imersao_ativas",
    "escolhas_do_perfil",
    "estilo_ativo",
    "fator_da_cena",
    "fica_no_degrau",
    "forca_do_bloco",
    "ligar_a_fonte_de_fora",
    "meus_toques_ativos",
    "modo_do_pad",
    "momentos_ativos",
    "momentos_em_efeito",
    "motor_do",
    "padrao_de",
    "pede_o_ouvido",
    "pico_do_pulso",
    "planos_do_perfil",
    "receita_do_estilo",
    "receita_do_perfil",
    "start_tato_vivo",
    "vibracao_do_gatilho_do_perfil",
]
