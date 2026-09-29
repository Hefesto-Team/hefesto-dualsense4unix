"""A háptica do cabo passa pelo lugar — A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01.

**O QUE MUDOU, 28/09/2026.** Pelo cabo o jogo tocava direto na placa de som do
controle, e o registro que o jogo lê (o device KS do prefixo) levava o
``BUSNUM-DEVNUM`` DAQUELE aparelho naquele instante: o cabo que chegava com o
jogo aberto não tinha bloco, e o que caía por ``-71`` e voltava com outro
``DEVNUM`` ficava com um bloco que não casava mais. E a escolha (b) dela
(``D-2709-A-VIBRACAO-VAI-A-QUEM-TEM-O-CONTROLE``: vibra quem está com o
controle na mão, no cabo e no rádio) não tinha onde se aplicar no cabo.

Agora o jogo casa o LUGAR (``endpoint_de_haptica``, um endpoint por lugar, de P1 a P4), e
este módulo leva o endpoint do lugar à placa do controle sentado nele: UM laço
por controle no cabo, do monitor do endpoint à placa, nos quatro canais, pelo
dono dos laços (``integrations/laco_de_audio.Lacos``, ``LATENCIA_MS``). Quando
o assento anda, o laço troca de endpoint e o jogo não perde nada; quando o
cabo volta com outro ``DEVNUM``, o laço aponta para a placa nova e o bloco do
lugar não muda.

A (b) NO CABO É O PORTÃO DO RÁDIO: os canais traseiros (os motores) passam só
para quem joga; os da frente (o alto-falante) passam sempre. O portão é o
volume do fluxo do laço na placa (``100% 100% 0% 0%`` para quem não joga), e
não dois laços: um laço de dois canais ``[ FL FR ]`` lendo um monitor de
quatro faria o PipeWire misturar os traseiros na frente, e o motor tocaria no
alto-falante.

O ALVO É O ``object.serial``, E NÃO O NOME (:func:`alvo_do_no`): pedido pelo
nome do monitor, o PipeWire liga o fluxo de captura à FONTE PADRÃO sem erro
nenhum — a fonte padrão desta máquina é o microfone do controle, e foi assim
que a ponte do rádio mandou a voz dela ao alto-falante (SOM-ECO-02, medido em
16/09/2026, ``alto_falante_bt.argv_do_gravador``). Pela mesma razão, quem
derruba o endpoint de um lugar solta o laço dele ANTES (:meth:`soltar`): um
laço cujo alvo some pode ser religado à fonte padrão.

E PEDIR SEM CONFERIR É A FORMA DO DEFEITO (a outra metade da SOM-ECO-02): na
volta seguinte à que ligou o laço, o lado de captura dele é conferido no grafo
(``alto_falante_bt.conferir_o_alvo_do_gravador``). Ligado a outro nó que não o
endpoint do lugar, o laço cai e aquela rota não se religa — a voz dela nunca
vai à placa do controle. Sem conseguir olhar, o laço fica e a volta seguinte
olha de novo: derrubar por não ter olhado trocaria um defeito raro por um mudo
garantido.

**O que não se mediu aqui:** o atraso do laço no controle na mão (o critério
de pronto pede dentro dos 50 ms do dono dos laços) e a vibração com o jogo
aberto. As duas são a prova no aparelho, e são dela.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.audio_ks_dualsense import (
    FAMILIA_DO_LACO_DO_CABO,
    MARCA_DO_LACO_DO_CABO,
    indice_do_fluxo,
)
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Os quatro canais do endpoint (``endpoint_de_haptica``, ``channel_map``): a
#: frente é o alto-falante, os traseiros são os motores. O MESMO mapa dos dois
#: lados do laço, para o PipeWire não remisturar nada.
CANAIS = 4
MAPA = "[ FL FR RL RR ]"

#: O portão dos motores, no volume do fluxo do laço. A frente passa sempre.
VOLUME_ABERTO = "100%"
VOLUME_FECHADO = "0%"

#: O dono dos laços desta família. Um só no processo: o ``atexit`` do
#: ``laco_de_audio`` fecha todas as famílias registradas no fecho.
_LACOS = Lacos(FAMILIA_DO_LACO_DO_CABO)


def no_de_captura(lugar: int) -> str:
    """O ``node.name`` do lado de captura do laço do lugar.

    O ``module-loopback`` do PipeWire chama os dois lados do laço de
    ``input.<nome>`` e ``output.<nome>`` quando só o ``--name`` é dado. **Não
    medido nesta máquina:** se o nome for outro, a conferência não acha o nó e
    responde «não sei» — o laço fica, e o diário diz que não se conferiu.
    """
    return f"input.{MARCA_DO_LACO_DO_CABO}{chave_do_lugar(lugar)}"


def chave_do_lugar(lugar: int) -> str:
    """A chave do laço no dono dos laços: ``lugar<n>``.

    Pelo LUGAR, e não pelo endereço: o nome do nó (``hefesto-haptica-do-cabo-
    lugar<n>``) aparece no grafo do PipeWire, e é por ele que o curador do
    registro acha a placa que o lugar serve (``audio_ks_dualsense.
    placas_servidas``).
    """
    return f"lugar{lugar}"


@dataclass(frozen=True)
class RotaDoCabo:
    """De onde o laço de um lugar lê e para onde ele toca — os dois por serial."""

    #: O endpoint do lugar: o fluxo de captura mirado nele lê o monitor.
    captura: str
    #: A placa do controle sentado no lugar.
    destino: str
    #: O ``node.name`` do endpoint do lugar: é a ele que o lado de captura do
    #: laço tem de estar ligado. Vazio = não se confere.
    origem: str = ""


def alvo_do_no(nome: str) -> str:
    """O alvo com que o ``pw-loopback`` acerta o nó: o ``object.serial``. "" = não há.

    SOM-ECO-02 (16/09/2026): pelo NOME, o fluxo de captura caía na fonte
    padrão quando o nó estava suspenso, e pelo serial acertava. O serial só é
    o índice do ``pactl`` quando quem responde é o ``pipewire-pulse``
    (``alto_falante_bt.o_servidor_e_o_pipewire``); sem ele não há
    ``pw-loopback`` que sirva, e a resposta honesta é "".
    """
    from hefesto_dualsense4unix.integrations.alto_falante_bt import (
        o_servidor_e_o_pipewire,
        serial_do_no,
    )

    if not nome or not o_servidor_e_o_pipewire():
        return ""
    serial = serial_do_no(nome)
    return "" if serial is None else str(serial)


class HapticaDoCabo:
    """Os laços do cabo, um por lugar ocupado por um DualSense no cabo.

    O estado do laço é do PROCESSO (o dono dos laços pergunta ao ``poll()``); o
    que se guarda aqui é só o que cada laço foi pedido para ligar e o portão
    que já se aplicou — para não reescrever o volume a cada volta.
    """

    def __init__(
        self,
        lacos: Any = None,
        *,
        indice_do_fluxo: Callable[[str], str | None] | None = None,
        pactl: Callable[[list[str]], str | None] | None = None,
        conferir: Callable[[str], str | None] | None = None,
    ) -> None:
        self._lacos: Any = lacos if lacos is not None else _LACOS
        self._indice_do_fluxo = indice_do_fluxo
        self._pactl = pactl
        self._conferir_alvo = conferir
        self._rotas: dict[int, RotaDoCabo] = {}
        #: lugar -> o portão que JÁ se aplicou (``True`` = motores abertos).
        self._portao: dict[int, bool] = {}
        #: Os lugares cujo laço já se viu ligado ao endpoint certo.
        self._conferidos: set[int] = set()
        #: lugar -> a rota que se ligou a outro nó: ela não se religa.
        self._recusadas: dict[int, RotaDoCabo] = {}

    def lugares(self) -> dict[int, RotaDoCabo]:
        """Os lugares com laço pedido, e a rota de cada um. Leitura."""
        return dict(self._rotas)

    def portao(self, lugar: int) -> bool | None:
        """O portão aplicado ao laço do lugar: aberto, fechado ou ``None`` (não aplicado)."""
        return self._portao.get(lugar)

    def casar(self, rotas: Mapping[int, RotaDoCabo], abertos: Iterable[int]) -> None:
        """Os laços ficam os de ``rotas``, e os motores abertos os de ``abertos``.

        Quem saiu de ``rotas`` perde o laço; quem mudou de rota (o assento que
        andou, a placa nova do cabo que voltou) é religado; e o portão de cada
        um é aplicado quando muda. **Nunca levanta**: é a volta do daemon.
        """
        querem_abrir = set(abertos)
        for lugar in [n for n in self._rotas if n not in rotas]:
            self.soltar(lugar)
        for lugar, rota in rotas.items():
            chave = chave_do_lugar(lugar)
            if self._recusadas.get(lugar) == rota:
                continue
            self._recusadas.pop(lugar, None)
            ja_estava = self._rotas.get(lugar) == rota and self._lacos.esta_ligado(chave)
            if ja_estava and lugar not in self._conferidos and not self._conferir(lugar, rota):
                continue
            if not ja_estava:
                self.soltar(lugar)
                if not self._lacos.ligar(
                    chave, captura=rota.captura, destino=rota.destino, canais=CANAIS, mapa=MAPA
                ):
                    logger.info("haptica_do_cabo_laco_nao_subiu", lugar=lugar)
                    continue
                self._rotas[lugar] = rota
                logger.info("haptica_do_cabo_laco_de_pe", lugar=lugar)
            aberto = lugar in querem_abrir
            if self._portao.get(lugar) is not aberto and self._aplicar_o_portao(lugar, aberto):
                self._portao[lugar] = aberto

    def _conferir(self, lugar: int, rota: RotaDoCabo) -> bool:
        """O lado de captura do laço está no endpoint do lugar? ``False`` = caiu.

        Chamado só na volta SEGUINTE à que ligou o laço: a ligação no grafo não
        é instantânea, e olhar cedo demais leria «não sei» à toa.
        """
        if not rota.origem:
            return True
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            conferir_o_alvo_do_gravador,
        )

        olhar = self._conferir_alvo or conferir_o_alvo_do_gravador
        try:
            ligado = olhar(no_de_captura(lugar))
        except Exception as exc:  # nunca derruba a volta
            logger.debug("haptica_do_cabo_conferencia_falhou", lugar=lugar, err=str(exc))
            ligado = None
        if ligado is None:
            logger.debug("haptica_do_cabo_nao_conferido", lugar=lugar)
            return True
        if ligado == rota.origem:
            self._conferidos.add(lugar)
            return True
        # O nome do nó errado não vai ao diário: pode ser o microfone dela,
        # que carrega o rabo do endereço do controle.
        logger.warning("haptica_do_cabo_ligado_a_outro_no", lugar=lugar)
        self.soltar(lugar)
        self._recusadas[lugar] = rota
        return False

    def _aplicar_o_portao(self, lugar: int, aberto: bool) -> bool:
        """O volume do fluxo do laço na placa: a frente cheia, os motores pelo portão.

        ``False`` quando o fluxo ainda não apareceu no servidor (o laço acabou
        de subir) ou o ``pactl`` não respondeu: a volta seguinte tenta de novo.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

        correr = self._pactl or rodar_pactl
        marca = MARCA_DO_LACO_DO_CABO + chave_do_lugar(lugar)
        try:
            if self._indice_do_fluxo is not None:
                indice = self._indice_do_fluxo(marca)
            else:
                # A leitura é a do curador (a mesma marca que ele lê para o
                # registro), feita pela porta do daemon, que pergunta ao retrato.
                indice = indice_do_fluxo(marca, rodar_pactl)
            if indice is None:
                return False
            motores = VOLUME_ABERTO if aberto else VOLUME_FECHADO
            resposta = correr([
                "pactl", "set-sink-input-volume", indice,
                VOLUME_ABERTO, VOLUME_ABERTO, motores, motores,
            ])
        except Exception as exc:  # nunca derruba a volta
            logger.debug("haptica_do_cabo_portao_falhou", lugar=lugar, err=str(exc))
            return False
        if resposta is None:
            return False
        logger.info("haptica_do_cabo_portao", lugar=lugar, motores_abertos=aberto)
        return True

    def soltar(self, lugar: int) -> None:
        """O laço do lugar cai. Idempotente — e vem ANTES de o endpoint cair."""
        self._lacos.desligar(chave_do_lugar(lugar))
        if self._rotas.pop(lugar, None) is not None:
            logger.info("haptica_do_cabo_laco_solto", lugar=lugar)
        self._portao.pop(lugar, None)
        self._conferidos.discard(lugar)

    def parar(self) -> None:
        """Todos os laços caem (o ``stop`` do subsystem)."""
        for lugar in list(self._rotas):
            self.soltar(lugar)


__all__ = [
    "CANAIS",
    "MAPA",
    "VOLUME_ABERTO",
    "VOLUME_FECHADO",
    "HapticaDoCabo",
    "RotaDoCabo",
    "alvo_do_no",
    "chave_do_lugar",
    "no_de_captura",
]
