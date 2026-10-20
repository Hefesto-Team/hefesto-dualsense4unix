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
import threading
import time
from array import array
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, replace
from typing import TYPE_CHECKING, Any, Protocol

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.core.physical_report_reader import TRIGGER_ESTADO_DISPAROU
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.lifecycle import (
    MODO_DUALSENSE,
    MODO_NATIVO,
    MODO_XBOX,
    modo_do_pad,
    o_hefesto_fala_no_modo,
)
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao
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
#: Os motores do rumble (o padrão da lista «Padrão dos motores»). Fora de ``CANAIS`` de propósito:
#: o jogo é dono deles quando vibra, e a regra é a de ``decidir`` com o carimbo do rumble.
CANAL_MOTORES = "motores"

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
    CANAL_MOTORES: "rumble",
}


JANELA_DO_JOGO_S = 3.0
TETO_POR_CONTROLE = 12
TETO_TOTAL = 40
JANELA_DO_TETO_S = 1.0
INTERVALO_S = 1.0 / 60.0
RELEITURA_DA_RECEITA_S = 1.0
#: O Som no corpo guarda no máximo este tanto de pedaços entre dois tiques (o resto é mais velho)
CORPO_MAX_PEDACOS = 16

CAMPO_DA_RECEITA = "receita_do_tato"

TIPO_DEDO = "dedo"
TIPO_RUMBLE = "rumble_tiro"
TIPO_SOM = "som_tiro"
#: O dedo largou o gatilho (``energia``: o quanto ele apertou). É o recuo: o Coice toca aqui.
TIPO_SOLTA = "solta_tiro"
#: A borda do som do jogo levada a TODOS os controles da mesa: a batida da música é de todos.
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
    #: quanto o dedo ficou apertado, na largada (``TIPO_SOLTA``); zero nos demais eventos
    duracao_s: float = 0.0


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
    #: algum gatilho do perfil tem imersão com momentos (OS-MOMENTOS-DA-IMERSAO-TOCAM-NO-GATILHO-01)
    momentos_da_imersao: bool = False
    #: algum controle do perfil escolheu uma forma de toque (Impacto, Guarda…): o toque do tiro
    #: dispara mesmo sem o estilo pedir (A forma é da pessoa, o disparo segue a receita.)
    efeitos_escolhidos: bool = False
    #: algum controle do perfil escolheu o Som no corpo (o grave do jogo, contínuo)
    som_no_corpo_escolhido: bool = False
    #: o estilo pede o Grão (os grãos finos da Simulação) e o Motor de época (o zumbido do Retrô):
    #: contínuos do laço, como o Som no corpo, mas sem som do jogo para ouvir
    grao_escolhido: bool = False
    motor_de_epoca_escolhido: bool = False
    #: algum controle do perfil escolheu um padrão para os motores (Tranco, Coice…)
    padroes_escolhidos: bool = False
    #: algum controle escolheu a Pancada do lado: o ouvido do som do jogo precisa subir
    pancada_escolhida: bool = False

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
#: A luz do estilo que respira ou pisca pulsa a cada tiro; a da batida sobe no som do jogo;
#: a parada não reage.
REACAO_DA_LUZ_DO_ESTILO: dict[str, str] = {
    "parada": "parada",
    "respira": "pulsa",
    "pisca": "pulsa",
    "batida": "batida",
}
#: A duração do toque do motor é a do estilo na escala do toque: os 200 ms de sempre do estilo
#: são os 40 ms do toque, e o dobro do Terror bate no teto de 60 (o limite de `Receita.de`).
TOQUE_DE_SEMPRE_MS = 40
TOQUE_MINIMO_MS = 25
TOQUE_MAXIMO_MS = 60
#: Os estilos de arma de rajada: só neles o gatilho acompanha o ritmo do tiro.
ESTILOS_DE_RAJADA = frozenset({"fps"})
#: O estalo do tiro no alto-falante do controle nasce desligado em todo estilo.
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
        # o que o estilo pede (19/10/2026): o Som no corpo da Corrida e da Simulação e o padrão dos
        # motores de cada estilo ligam o motor sem escolha nenhuma do usuário
        som_no_corpo_escolhido=(
            formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.SOM_NO_CORPO),
        grao_escolhido=formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.GRAO,
        motor_de_epoca_escolhido=(
            formas_de_haptica.POR_ESTILO.get(estilo.chave) == formas_de_haptica.MOTOR_DE_EPOCA),
        padroes_escolhidos=padrao is not None,
        pancada_escolhida=padrao == "pancada_do_lado",
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

    Só entra quem escolheu: «Do estilo» e o perfil sem opinião ficam fora, e o controle sem
    escolha se comporta como sempre. Escolha que não se lê também fica fora.
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
            # o Grão e o Motor de época que a pessoa escolhe na lista (20/10/2026) ligam o laço
            # contínuo como os do estilo
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
                v != padroes_de_vibracao.SEM_EFEITO for v in padroes.values()),
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
        #: as imersões com momentos de cada gatilho do perfil ativo, relidas com a receita.
        self.momentos: MapaDosMomentos = SEM_MOMENTOS
        #: a forma de toque que cada controle do perfil ativo escolheu (por ``norm_mac``)
        self.escolhas: dict[str, str] = {}
        #: o padrão dos motores que cada controle escolheu (por ``norm_mac``)
        self.escolhas_de_imersao: dict[str, str] = {}
        #: onde o gatilho do perfil ativo vibra (o padrão dos motores espera a soltura)
        self.vibra_o_gatilho: VibracaoDoGatilho = SEM_VIBRACAO
        #: quando o jogo pediu rumble pelo pad ``uinput`` (por ``norm_mac``): esse pad não tem
        #: ``visto_ha_s``, e sem isto o padrão dos motores tocaria por cima do jogo no modo Xbox.
        self.rumble_visto_em: dict[str, float] = {}
        #: o status do Disparo de cada gatilho (0 antes, 1 dentro, 2 passou do clique), lido do
        #: report de entrada; sem entrada é que o aparelho não o disse (o relógio vale).
        self.disparo: dict[tuple[str, str], int] = {}
        #: a volta dos acessórios (toque, luzinhas e pulso da barra); anda sem receita e sem jogo
        self.volta: Any = None
        #: os meus toques (a vibração a cada entrada de quem joga); anda sem receita
        self.meus_toques: Any = None

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
        da imersão) olha cada um deles a cada tique, com ou sem evento.
        """
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
        #: o quanto o dedo apertou, por gatilho, até largar
        self._pico: dict[tuple[str, str], int] = {}
        #: quando cada gatilho foi apertado (a duração do aperto vai no evento da largada)
        self._inicio: dict[tuple[str, str], float] = {}
        #: as largadas ainda não levadas ao motor (``tirar_as_soltas``); ``ver`` não as devolve
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
        # Reatribuído, nunca mutado: escreve a thread do pad e lê a do tique.
        motor.rumble_visto_em = {**motor.rumble_visto_em, norm_mac(uniq) or uniq: instante}
        for evento in motor.borda_do_rumble.ver(uniq, fraco, forte, instante, efetivo):
            motor.anotar(evento)
    except Exception:
        logger.debug("tato_vivo_borda_do_rumble_falhou", exc_info=True)


# O-TIRO-VEM-DO-LADO-CERTO-01: o estalo do som do jogo dá o lado do toque. O som é
# um fluxo só para a mesa inteira: com um controle, o estalo é dele; com mais de
# um, vai só a quem atirou naquela janela (o tiro do inimigo não tem dono).
JANELA_DO_DISPARO_S = 0.3  # do aperto ao estalo: o quadro do jogo, o buffer e o gravador


def pede_o_ouvido(receita: Receita) -> bool:
    """A receita precisa do som do jogo: o lado, o estalo, o corpo, a pancada ou a batida."""
    return bool(
        receita.lado_do_som or receita.som_no_controle or receita.som_no_corpo_escolhido
        or receita.pancada_escolhida or receita.reacao_ao_tiro == REACAO_BATIDA)


def destinos_do_som(
    controles: Sequence[Controle], dedo: BordaDoDedo, instante: float
) -> list[str]:
    """Os controles a quem o estalo do som do jogo pertence."""
    if len(controles) == 1:
        return [controles[0].uniq]
    return [c.uniq for c in controles if dedo.atirando(c.uniq, instante)]


#: O Eco só reverbera o golpe forte; o fraco toca o Impacto, sem a cauda grave.
ECO_A_PARTIR_DE = 0.7


class AtuadorDaHaptica:
    """O toque do tiro, na forma que o controle escolheu, no tocador do rumble dele.

    Sem escolha (ou em «Do estilo») o toque é o de hoje. A escolha explícita dispara nos mesmos
    eventos da receita; «Sem efeito» e o Som no corpo (contínuo, do laço) não respondem a evento.
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
    ) -> None:
        self._tocar = tocar
        self._ouvindo = ouvindo or (lambda: False)
        self._escolha_de = escolha_de or (lambda uniq: None)
        self._estilo_de = estilo_de or (lambda: None)
        self._na_economia = na_economia or (lambda uniq: False)
        self._nota_de = nota_de or (lambda uniq: None)

    def _toque_da_unidade(self, uniq: str) -> str:
        """O Toque na nota da cor do plástico (a Assinatura), na mesma regra da Chegada: todo
        estilo menos o Nativo e o Personalizado; o Toque de 160 Hz fora dela ou sem nota."""
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
        escolha = formas_de_haptica.escolha_valida(self._escolha_de(evento.uniq))
        if escolha == formas_de_haptica.SEM_EFEITO or escolha in formas_de_haptica.CONTINUAS:
            return False
        # o estilo que não toca ou que toca o corpo inteiro, de forma contínua (a Corrida, a
        # Simulação, o Retrô): sem toque de tiro
        forma_do_estilo = formas_de_haptica.forma_do_estilo(self._estilo_de())
        if escolha is None and (forma_do_estilo == formas_de_haptica.SEM_EFEITO
                                or forma_do_estilo in formas_de_haptica.CONTINUAS):
            return False
        if evento.tipo == TIPO_SOM:
            return receita.lado_do_som
        quer = receita.vibracao_por_tiro or escolha is not None
        if evento.tipo != TIPO_RUMBLE or not quer:
            return False
        # Um tiro, um toque: com o ouvido no som do jogo, o toque (e o lado) vem do estalo.
        return not (receita.lado_do_som and self._ouvindo())

    def escrever(self, evento: Evento, receita: Receita, agora: float) -> float | None:
        forma = self._forma(evento.uniq)
        if forma is None:
            return None
        pedido = (
            evento.uniq,
            evento.energia * receita.forca_do_toque,
            evento.lado,
            receita.duracao_do_toque_ms,
        )
        if forma == formas_de_haptica.ECO and evento.energia < ECO_A_PARTIR_DE:
            forma = formas_de_haptica.IMPACTO  # só o golpe forte reverbera
        if forma == formas_de_haptica.TOQUE:
            forma = self._toque_da_unidade(evento.uniq)
        if forma == formas_de_haptica.TOQUE:
            self._tocar(*pedido)
        else:
            self._tocar(*pedido, forma)
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


def _padroes_do_modo(nome: str) -> dict[str, int]:
    """Os números de partida de um modo da tela (`trigger_specs.PRESETS`)."""
    from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec

    spec = get_spec(nome)
    return {p.name: p.default for p in spec.params} if spec is not None else {}


def _bloco_cru(nome: str, valores: Mapping[str, int]) -> bytes:
    """O bloco cru de 11 bytes de um modo com estes números, no layout que o relatório leva."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    efeito = build_from_name(nome, {**_padroes_do_modo(nome), **valores})
    f = efeito.forces
    # O relatório leva o `forces[6]` no décimo byte do bloco (`common[19]` do backend).
    return bytes([efeito.mode, f[0], f[1], f[2], f[3], f[4], f[5], 0, 0, f[6], 0])


def bloco_do_gatilho(modo: str, receita: Receita) -> bytes:
    """O bloco cru de 11 bytes do preset da tela, no layout que o relatório leva."""
    valores: dict[str, int] = {}
    if modo == GATILHO_RAJADA:
        valores["frequency"] = receita.frequencia_da_rajada_hz
    return _bloco_cru(_PRESET_DO_GATILHO[modo], valores)


def bloco_do_clique() -> bytes:
    """O bloco cru do Clique · mouse (o clique raso do começo do curso): o da Chegada."""
    from hefesto_dualsense4unix.profiles.efeitos_de_imersao import POR_CHAVE, ajustes_da_imersao

    return _bloco_cru("Weapon", ajustes_da_imersao(POR_CHAVE["clique-mouse"], "Weapon") or {})


class AtuadorDoGatilho:
    """Arma ou rajada, por lado e por controle, conforme o intervalo entre tiros."""

    canal = CANAL_GATILHO

    def __init__(
        self,
        escrever: Callable[[str, str, bytes], object],
        devolver: Callable[[str], object],
        apertado: Callable[[str, str], bool] | None = None,
        largar: Callable[[str], object] | None = None,
        cede: Callable[[str, str], bool] | None = None,
        soltar_lado: Callable[[str, str, bytes], object] | None = None,
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        #: o lado em que a pessoa escolheu uma imersão com momentos é dos momentos
        self._cede = cede
        #: devolve UM lado ao perfil, sem encerrar a sessão (que um momento pode segurar)
        self._soltar_lado = soltar_lado
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
            # A arma automática: um aperto só, e o jogo pede o motor a cada bala.
            lados = [lado for lado in _LADO_DO_BACKEND if self.apertado(evento.uniq, lado)]
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
            bloco = bloco_do_gatilho(modo, receita)
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
        # A sessão não saiu: um momento do OUTRO lado a segura. O lado do ritmo volta ao perfil
        # sozinho (só se ainda for o bloco do ritmo), em vez de ficar preso junto com a sessão.
        for disco, bloco in blocos.items():
            self._soltar_lado(uniq, disco, bloco)


# OS-MOMENTOS-DA-IMERSAO-TOCAM-NO-GATILHO-01 (15/10/2026): o tempo do aperto.
# A imersão que a pessoa escolhe na aba Gatilhos vai ao perfil só como os números do
# acionamento, e se reconhece por eles (`imersao_dos_numeros`, a mesma regra da tela).
# Os `momentos` dela mudam o bloco do gatilho com o tempo: ao apertar, segurando
# (depois de `apos_ms`, repetindo a cada `a_cada_ms`) e sempre, cada um até `dura_ms`.
# As regras do motor valem sem exceção: o jogo que escreve o gatilho cala o momento,
# o Modo Nativo cala, e cada escrita passa pelo teto.
QUANDO_AO_APERTAR = "ao_apertar"
QUANDO_SEGURANDO = "segurando"
QUANDO_SEMPRE = "sempre"
#: O «sempre» sem `dura_ms` não segura a sessão para sempre: passado o teto, expira e a devolve.
TETO_DO_SEMPRE_S = 300.0
#: a chave do momento na sessão do motor; o ritmo do tiro tem a sua, no mesmo gatilho.
CANAL_DO_MOMENTO = "momento"


@dataclass(frozen=True)
class PlanoDoGatilho:
    """A imersão de um lado de um controle: o acionamento, os números e os momentos dele."""

    imersao: Imersao
    #: o acionamento cujos números o momento ajusta
    modo: str
    #: o estilo da variante que casou (``""`` na base): é a dele que vale nos outros modos
    estilo: str
    ajustes: Mapping[str, int]
    #: só os que valem no `modo` (o `valem_em` de cada um)
    momentos: tuple[Momento, ...]
    #: o Modo automático põe «Sem efeito» no aparelho: a volta à mão é o ``Off``
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

    #: lado (`esquerdo`/`direito`) → plano
    geral: Mapping[str, PlanoDoGatilho] = field(default_factory=dict)
    #: controle (`norm_mac`) → lado escrito → plano, ou ``None`` se o lado dele não tem imersão
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
    mostra a imersão dela, e o motor toca os momentos dela. A volta à mão é o bloco do PERFIL,
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

    O ``Lado`` do estilo diz a imersão do gatilho (``R2`` e ``L2`` são receitas separadas); sem ela
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


def planos_do_perfil(perfil: Any) -> MapaDosMomentos:
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

    if modo == MODO_AUTOMATICO:
        estilo = _ler(perfil, "estilo")
        if not isinstance(estilo, str):
            return SEM_MOMENTOS
        planos = {lado: _plano_do_automatico(estilo, lado) for lado in _LADO_DO_BACKEND}
        return MapaDosMomentos({lado: p for lado, p in planos.items() if p is not None})
    geral = {lado: plano for lado, disco in _LADO_DO_BACKEND.items()
             if (plano := _plano_do_lado(_ler(gatilhos, disco))) is not None}
    por_controle: dict[str, dict[str, PlanoDoGatilho | None]] = {}
    for chave, seus, lados in escritos:
        alvo = norm_mac(chave)
        if alvo:
            por_controle[alvo] = {lado: _plano_do_lado(_ler(seus, disco))
                                  for lado, disco in _LADO_DO_BACKEND.items() if disco in lados}
    return MapaDosMomentos(geral, por_controle)


#: Os acionamentos em que o gatilho vibra por conta própria (a Metralhadora e a vibração por
#: posição): com um deles em ação, o padrão dos motores espera a soltura do tiro.
MODOS_QUE_VIBRAM = frozenset(FAMILIAS["metralhadora"]) | frozenset(
    FAMILIAS["vibração por posição"])


@dataclass(frozen=True)
class VibracaoDoGatilho:
    """Em que controles o gatilho do perfil vibra (algum dos dois lados)."""

    geral: bool = False
    #: controle (``norm_mac``) → vibra, quando ele escreve os gatilhos por cima do global
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


def vibracao_do_gatilho_do_perfil(perfil: Any) -> VibracaoDoGatilho:
    """Onde o gatilho do perfil vibra: no automático, o acionamento do estilo; senão, o escrito."""
    lidos = _gatilhos_do_perfil(perfil)
    if lidos is None:
        return SEM_VIBRACAO
    gatilhos, escritos, modo = lidos
    from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO

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
    está: quem escreve olha o bloco, não ela.
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
    ) -> None:
        self._escrever = escrever
        self._devolver = devolver
        self.apertado = apertado
        self._largar = largar
        #: a Bateria longa vale neste controle? Os momentos param e fica o bloco de economia
        self._na_economia = na_economia
        #: o status do Disparo (0, 1, 2) deste lado, ou ``None`` se o aparelho não o disse
        self._disparo = disparo
        self._aperto: dict[tuple[str, str], float] = {}
        self._clique: dict[tuple[str, str], float] = {}
        self._sempre: dict[tuple[str, str], tuple[PlanoDoGatilho, float]] = {}
        #: o «sempre» sem fim que passou do teto: fica fora até a imersão mudar ou ser devolvida
        self._expirou: set[tuple[str, str]] = set()
        #: a marca do que está escrito é o BLOCO, não a volta do relógio em que ele saiu
        self._escrito: dict[tuple[str, str], bytes] = {}
        self._planos: dict[tuple[str, str], PlanoDoGatilho] = {}
        #: controles cuja sessão o momento segura entre as batidas de um «sempre»
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
            self.soltar(saiu)  # o controle saiu da mesa: não há o que devolver nele
        for uniq in uniqs:
            estado = estado_de(uniq)
            if estado is None or not decidir(CANAL_GATILHO, estado):
                if estado is not None and _o_modo_cala_o_motor(estado):
                    # O motor calou (sem jogo, alt-tab, modo em que o Hefesto não fala): o
                    # bloco do momento não pode ficar no aparelho.
                    self.devolver(uniq, agora)
                elif self._na_sessao(uniq):
                    # O jogo escreve o gatilho: o momento se cala e o valor é dele.
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
                    self._clique[chave] = agora  # a primeira vez que o clique passou
            else:
                self._aperto.pop(chave, None)
                self._clique.pop(chave, None)

    def _tocar(self, motor: TatoVivo, uniq: str, planos: MapaDosMomentos, agora: float) -> int:
        self._ver_o_dedo(uniq, agora)
        economia = self._economia(uniq)
        escritas = 0
        a_voltar: list[str] = []
        for lado, disco in _LADO_DO_BACKEND.items():
            chave = (uniq, lado)
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
            self._voltar(uniq, ())  # a imersão saiu entre duas batidas: a sessão volta
            motor.contadores["devolucoes"] += 1
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
        # Outro canal do motor segura a sessão: o estático vai à mão, e a sessão é dele.
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
            self._sempre.pop(chave, None)  # o «sempre» recomeça quando o jogo largar
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
            self._sempre.pop(chave, None)  # antes da volta: sem plano, nenhuma batida segura
            self._expirou.discard(chave)
            self._clique.pop(chave, None)
        if self._na_sessao(uniq):
            self._voltar(uniq, self.segura(uniq))

    def devolver_tudo(self, agora: float) -> None:
        """O motor parou: cada controle em que o momento segura a sessão volta ao perfil."""
        self._aperto.clear()
        for uniq in {u for u, _lado in self._escrito} | set(self._entre_batidas):
            self.devolver(uniq, agora)


# O-EFEITO-IMERSAO-DOS-MOTORES-GANHA-A-LISTA-NOVA-01 (15/10/2026): o padrão dos motores.
# O padrão (Tranco, Batida, Onda, Coice, Pancada do lado) toca no mesmo tiro da receita, nos
# motores do rumble, por escolha da pessoa. O jogo manda: se ele vibra o motor (o carimbo do
# rumble), o padrão cala. O gatilho que vibra (Metralhadora e vizinhas) só deixa o padrão tocar
# na soltura do tiro, nunca durante a rajada.
COICES_POR_S = 3
JANELA_DO_COICE_S = 1.0
FORCA_NA_ECONOMIA = FORCA_DO_DEGRAU["economia"]
FOLGA_DA_VOLTA_S = 0.15  # depois do último passo, a volta zera os motores se o relógio falhou
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
    #: o último par escrito (fraco, forte): o zero do fim não se escreve duas vezes
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
        gatilho_vibra: Callable[[str], bool],
        forca_de: Callable[[str], float],
        estilo_de: Callable[[], Any] | None = None,
    ) -> None:
        #: ``escrever(uniq, fraco, forte)``: o motor direito é o fraco, o esquerdo o forte
        self._escrever = escrever
        self._estilo_de = estilo_de or (lambda: None)
        self._padrao_de = padrao_de
        self._gatilho_vibra = gatilho_vibra
        self._forca_de = forca_de
        self._em_curso: dict[str, _PadraoEmCurso] = {}
        self._coices: dict[str, deque[float]] = {}

    def _cabe_o_coice(self, uniq: str, instante: float) -> bool:
        fila = self._coices.setdefault(uniq, deque())
        while fila and instante - fila[0] >= JANELA_DO_COICE_S:
            fila.popleft()
        return len(fila) < COICES_POR_S

    def responde_a(self, evento: Evento, receita: Receita) -> bool:
        if evento.tipo not in (TIPO_DEDO, TIPO_SOM, TIPO_SOLTA) or evento.uniq in self._em_curso:
            return False
        padrao = self._padrao_de(evento.uniq)
        if padrao is None:
            return False
        vibra = receita.gatilho_no_ritmo or self._gatilho_vibra(evento.uniq)
        regra = padroes_de_vibracao.na_soltura_do_estilo(padrao, self._estilo_de())
        if vibra or padrao in padroes_de_vibracao.NA_SOLTURA or regra is not None:
            if evento.tipo != TIPO_SOLTA:
                return False
            if regra is not None and (
                    evento.duracao_s < regra.segurado_s
                    or (regra.lado is not None and evento.lado != regra.lado)):
                return False  # a Onda do Furtivo só sai de quem segurou a mira
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
        motores = padroes_de_vibracao.AMBOS
        if padrao in padroes_de_vibracao.DO_LADO_DO_SOM:
            motores = _MOTOR_DO_LADO.get(evento.lado, padroes_de_vibracao.AMBOS)
        if padrao in padroes_de_vibracao.NA_SOLTURA:
            self._coices.setdefault(uniq, deque()).append(evento.instante)
        passos = padroes_de_vibracao.sequencia(padrao, motores)
        self._em_curso[uniq] = _PadraoEmCurso(passos, agora, self._forca_de(uniq))
        self._andar(uniq, agora)
        return agora + padroes_de_vibracao.duracao_ms(padrao) / 1000.0 + FOLGA_DA_VOLTA_S

    def _andar(self, uniq: str, agora: float) -> None:
        """Escreve o passo em que o relógio está; no fim, zera os motores e solta o padrão."""
        curso = self._em_curso.get(uniq)
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
                    self._escrever(uniq, *curso.escrito)
                return
        self._zerar(uniq)

    def _zerar(self, uniq: str) -> None:
        curso = self._em_curso.pop(uniq, None)
        if curso is not None and curso.escrito != (0, 0):
            self._escrever(uniq, 0, 0)

    def relogio(
        self,
        motor: TatoVivo,
        agora: float,
        uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
        receita: Receita,
    ) -> int:
        escritas = 0
        for uniq in list(self._em_curso):
            if uniq not in uniqs or estado_de(uniq) is None:
                # O controle saiu da mesa. (O jogo que passa a vibrar é do ``tique``: a volta
                # pendente do padrão pergunta ``decidir`` e chama ``soltar``.)
                self._em_curso.pop(uniq, None)
                continue
            antes = self._em_curso[uniq].indice
            self._andar(uniq, agora)
            curso = self._em_curso.get(uniq)
            if curso is None or curso.indice != antes:
                escritas += 1
                motor.contadores["escritas"] += 1
        return escritas

    def soltar(self, uniq: str) -> None:
        """O jogo tomou os motores: o padrão deixa de valer, sem escrever nada."""
        self._em_curso.pop(uniq, None)

    def devolver(self, uniq: str, agora: float) -> None:
        self._zerar(uniq)

    def devolver_tudo(self, agora: float) -> None:
        for uniq in list(self._em_curso):
            self._zerar(uniq)


def _valor(passo: int, forca: float) -> int:
    return max(0, min(255, round(passo * forca)))


# A-LUZ-RESPIRA-A-CADA-TIRO-01: a barra pulsa (ou troca de cor) a cada tiro e volta.
# Teto de 3 subidas por segundo por controle (WCAG 2.3.1, três flashes por
# segundo), cobrado aqui e não só na tela: o tiro que chega com a luz ainda no
# pico estende o pico, e a rajada vira um brilho contínuo, nunca um pisca-pisca.
REACAO_PULSA = "pulsa"
REACAO_EVENTO = "evento"
#: a luz sobe na borda do som do jogo (`TIPO_BATIDA`), não no tiro: o Ritmo
REACAO_BATIDA = "batida"
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
        na_economia: Callable[[str], bool] | None = None,
    ) -> None:
        self._pintar = pintar
        self._cor_de = cor_de
        self._devolver = devolver
        self._largar = largar
        #: a Bateria longa vence o estilo: a barra fica fixa na cor do perfil, sem pulso
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
    #: o status do Disparo de ``(L2, R2)`` que o report de entrada trouxe; ``None`` se não veio
    estado_gatilho: tuple[int, int] | None = None


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
    controller = getattr(daemon, "controller", None)
    primario = getattr(controller, "primary_uniq", None)
    if isinstance(primario, str) and primario:
        estado = getattr(daemon, "_last_state", None)
        vistos[primario] = Controle(
            primario,
            getattr(daemon, "_gamepad_device", None),
            _inteiro(getattr(estado, "l2_raw", 0)),
            _inteiro(getattr(estado, "r2_raw", 0)),
            _status_do_disparo(getattr(daemon, "_motion_reader", None)),
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
            vistos[mac] = Controle(
                mac, getattr(jogador, "vpad", None), l2, r2,
                _status_do_disparo(getattr(jogador, "motion_reader", None)))
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


#: O nome que não achou arquivo com o slug dele e a receita que o `load_profile`
#: trouxe: o laço só volta a varrer quando o `active_profile` muda.
_PELO_CARREGADOR: tuple[str, Receita] | None = None
#: A vista do perfil que a última leitura da receita trouxe: os momentos saem dela,
#: sem ler o disco de novo.
_VISTA_LIDA: tuple[str, Any] | None = None


#: A vista do computador sem perfil nenhum: ``(o computador lido, a vista)``. O
#: ``o_computador()`` devolve o MESMO objeto até o ``maquina.json`` mudar, então o
#: laço de 60 Hz não valida o modelo de novo a cada leitura.
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
            perfil_que_vale,
            perfil_vazio,
        )

        computador = o_computador()
        feita = _VISTA_DO_COMPUTADOR
        if feita is None or feita[0] is not computador:
            feita = (computador, perfil_que_vale(perfil_vazio(), computador))
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
    (A-RECEITA-DO-TATO-SE-LE-SEM-SEMEAR-NEM-VARRER-01).
    """
    global _PELO_CARREGADOR, _VISTA_LIDA
    nome = _nome_do_perfil_ativo(daemon)
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


def momentos_ativos(daemon: Any) -> MapaDosMomentos:
    """Os planos dos momentos do perfil ativo, da vista que :func:`receita_ativa` leu."""
    nome = _nome_do_perfil_ativo(daemon)
    lida = _VISTA_LIDA
    if lida is None or lida[0] != nome:
        return SEM_MOMENTOS
    try:
        return planos_do_perfil(lida[1])
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
        return vibracao_do_gatilho_do_perfil(lida[1])
    except Exception:
        logger.debug("tato_vivo_vibracao_do_gatilho_ilegivel", exc_info=True)
        return SEM_VIBRACAO


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


def _na_barra(valor: int, pontos: int) -> int:
    return max(0, min(255, round(valor * pontos / 100.0)))


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
        return min(degrau, FORCA_NA_ECONOMIA) if na_economia(uniq) else degrau

    def motores(uniq: str, fraco: int, forte: int) -> object:
        escrever = getattr(controller, "set_rumble_for", None)
        if not callable(escrever):
            return False
        forte_pct, fraco_pct = _barras_dos_motores(daemon, uniq)
        return escrever(uniq, _na_barra(fraco, fraco_pct), _na_barra(forte, forte_pct))

    def momento(uniq: str, lado: str, bloco: bytes) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        if not callable(escrever):
            return False
        sessao.tomar(uniq, CANAL_DO_MOMENTO)
        return escrever(uniq, lado, bloco)

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
            lambda uniq: nota_da_unidade(daemon, uniq)),
        AtuadorDoSom(estalo),
        AtuadorDoGatilho(
            gatilho,
            lambda uniq: sessao.soltar(uniq, CANAL_GATILHO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_GATILHO),
            do_momento,
            soltar_lado,
        ),
        AtuadorDosMomentos(
            momento,
            lambda uniq: sessao.soltar(uniq, CANAL_DO_MOMENTO),
            apertado,
            lambda uniq: sessao.largar(uniq, CANAL_DO_MOMENTO),
            na_economia,
            disparo,
        ),
        AtuadorDaLuz(
            pintar,
            cor_de,
            lambda uniq: sessao.soltar(uniq, CANAL_LUZ),
            lambda uniq: sessao.largar(uniq, CANAL_LUZ),
            na_economia,
        ),
        AtuadorDosMotores(
            motores, padrao_de, gatilho_vibra, forca_do_padrao, lambda: estilo_ativo(daemon)),
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
        # O Som no corpo: o grave do jogo, filtrado na thread do ouvido e levado a cada tique.
        self._filtro_do_corpo = formas_de_haptica.FiltroDoCorpo()
        self._corpo: deque[Any] = deque(maxlen=CORPO_MAX_PEDACOS)
        # O Grão e o Motor de época: um gerador por controle (a semente e a fase são dele) e o
        # instante do último pedaço levado, por forma; quem deixa de ter dono recomeça do zero.
        self._graos: dict[str, formas_de_haptica.GeradorDoGrao] = {}
        self._motores_de_epoca: dict[str, formas_de_haptica.GeradorDoMotorDeEpoca] = {}
        self._continua_em: dict[str, float] = {}
        self._agora_da_continua = 0.0

    def receita_de_agora(self, agora: float) -> Receita:
        if agora - self._lida_em >= RELEITURA_DA_RECEITA_S:
            self._lida_em = agora
            self.receita_vigente = receita_ativa(self.daemon)
            self.motor.momentos = (
                momentos_ativos(self.daemon)
                if self.receita_vigente.momentos_da_imersao else SEM_MOMENTOS)
            self.motor.escolhas = escolhas_ativas(self.daemon)
            self.motor.escolhas_de_imersao = escolhas_de_imersao_ativas(self.daemon)
            self.motor.vibra_o_gatilho = vibracao_do_gatilho_ativa(self.daemon)
            if self.motor.meus_toques is not None:
                self.motor.meus_toques.ajustar(meus_toques_ativos(self.daemon))
        return self.receita_vigente

    def alimentar_o_corpo(self, pcm: bytes) -> None:
        """Chamado na thread do ouvido: o PCM do jogo vira o grave, se alguém o escolheu."""
        if self.receita_vigente.som_no_corpo_escolhido:
            self._corpo.append(self._filtro_do_corpo.processar(pcm))

    def _levar_o_corpo(
        self, receita: Receita, uniqs: Sequence[str],
        estado_de: Callable[[str], EstadoDoCanal | None],
    ) -> None:
        """O grave do jogo vai a cada controle que escolheu o Som no corpo e onde o jogo cala."""
        pedacos = []
        while self._corpo:
            try:
                pedacos.append(self._corpo.popleft())
            except IndexError:  # a thread do ouvido esvaziou a fila entre o teste e a retirada
                break
        if not pedacos or not receita.som_no_corpo_escolhido:
            return
        donos = []
        for uniq in uniqs:
            estado = estado_de(uniq)
            forma = formas_de_haptica.forma_que_vale(
                self.motor.escolhas.get(norm_mac(uniq) or ""), estilo_ativo(self.daemon))
            if (forma == formas_de_haptica.SOM_NO_CORPO
                    and estado is not None and decidir(CANAL_HAPTICA, estado)
                    and not _controle_na_economia(uniq)):
                donos.append(uniq)
        if not donos:
            return
        amostras = array("f")
        for pedaco in pedacos:
            amostras.extend(pedaco)
        alto_falante = getattr(self.daemon, "_alto_falante_subsystem", None)
        levar = getattr(alto_falante, "tocar_o_corpo", None)
        if not callable(levar):
            return
        for uniq in donos:
            levar(uniq, amostras)

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
            levar(uniq, amostras)

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
                    continue  # sem rumble do jogo não há zumbido a começar
                gerador = self._motores_de_epoca[uniq] = formas_de_haptica.GeradorDoMotorDeEpoca()
            elif nivel <= 0.0 and gerador.calado:
                del self._motores_de_epoca[uniq]  # o zumbido arrastou até o fim: acabou
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
            return 0
        self.motor.ligado = True
        controles = controles_do_daemon(self.daemon)
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
                estado_do_controle(c, jogo, self._sessao_ha_s(c, agora)),
                self.motor.rumble_visto_em.get(norm_mac(c.uniq) or c.uniq),
                agora,
            )
            for c in controles
        }
        escritas = self.motor.tique(agora, por_uniq.get, receita, uniqs=tuple(por_uniq))
        self._levar_o_corpo(receita, tuple(por_uniq), por_uniq.get)
        self._agora_da_continua = agora
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
        if pede_o_ouvido(receita):
            ouvido.comecar()
        batida = receita.reacao_ao_tiro == REACAO_BATIDA
        for estalo in ouvido.tirar():
            for uniq in destinos_do_som(controles, self.dedo, estalo.instante):
                self.motor.anotar(
                    Evento(estalo.instante, uniq, TIPO_SOM, estalo.lado, estalo.energia,
                           getattr(estalo, "recorte", None))
                )
            for controle in controles if batida else ():
                self.motor.anotar(
                    Evento(estalo.instante, controle.uniq, TIPO_BATIDA, estalo.lado,
                           estalo.energia))


async def tato_vivo_loop(daemon: DaemonProtocol, motor: TatoVivo) -> None:
    passo = Passo(daemon, motor)
    if motor.ouvido is None:
        from hefesto_dualsense4unix.integrations.transiente_do_jogo import OuvidoDoJogo

        motor.ouvido = OuvidoDoJogo(
            lambda: motor.ligado and pede_o_ouvido(passo.receita_vigente) and passo.jogo,
            recortar=lambda: passo.receita_vigente.som_no_controle,
            ao_pcm=passo.alimentar_o_corpo,
        )
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
    finally:
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
    "DESLIGADA",
    "MODO_DUALSENSE",
    "MODO_NATIVO",
    "MODO_XBOX",
    "Atuador",
    "AtuadorDaHaptica",
    "AtuadorDaLuz",
    "AtuadorDoGatilho",
    "AtuadorDoSom",
    "AtuadorDosMomentos",
    "AtuadorDosMotores",
    "BordaDoDedo",
    "BordaDoRumble",
    "Controle",
    "EstadoDoCanal",
    "Evento",
    "MapaDosMomentos",
    "Passo",
    "PlanoDoGatilho",
    "Receita",
    "SessaoDoMotor",
    "TatoVivo",
    "Teto",
    "VibracaoDoGatilho",
    "anotar_o_rumble",
    "bloco_do_gatilho",
    "controles_do_daemon",
    "decidir",
    "destinos_do_som",
    "duracao_do_toque_do_estilo",
    "escolhas_ativas",
    "escolhas_de_imersao_ativas",
    "escolhas_do_perfil",
    "estilo_ativo",
    "meus_toques_ativos",
    "modo_do_pad",
    "momentos_ativos",
    "momentos_em_efeito",
    "motor_do",
    "pede_o_ouvido",
    "pico_do_pulso",
    "planos_do_perfil",
    "receita_do_estilo",
    "receita_do_perfil",
    "start_tato_vivo",
    "vibracao_do_gatilho_do_perfil",
]
