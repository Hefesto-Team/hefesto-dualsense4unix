"""A háptica do cabo passa pelo endpoint do aparelho — A-HAPTICA-E-POR-APARELHO-01.

**O QUE MUDOU, 28/09/2026.** Pelo cabo o jogo tocava direto na placa de som do
controle, e o registro que o jogo lê (o device KS do prefixo) levava o
``BUSNUM-DEVNUM`` DAQUELE aparelho naquele instante: o cabo que chegava com o
jogo aberto não tinha bloco, e o que caía por ``-71`` e voltava com outro
``DEVNUM`` ficava com um bloco que não casava mais. E a escolha (b) dela
(``D-2709-A-VIBRACAO-VAI-A-QUEM-TEM-O-CONTROLE``: vibra quem está com o
controle na mão, no cabo e no rádio) não tinha onde se aplicar no cabo.

O jogo casa o endpoint do APARELHO (``endpoint_de_haptica``, um por DualSense
desde 02/10/2026; de 28/09 a 02/10 era um por lugar), e este módulo o leva à
placa do controle: UM laço por controle no cabo, do monitor do endpoint à
placa, nos quatro canais, pelo dono dos laços
(``integrations/laco_de_audio.Lacos``, ``LATENCIA_MS``). A chave do laço é a
marca do aparelho: renumerar a mesa não troca laço nenhum, e quando o cabo
volta com outro ``DEVNUM`` o laço aponta para a placa nova e o bloco do
aparelho não muda.

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
derruba o endpoint de um aparelho solta o laço dele ANTES (:meth:`soltar`): um
laço cujo alvo some pode ser religado à fonte padrão.

E PEDIR SEM CONFERIR É A FORMA DO DEFEITO (a outra metade da SOM-ECO-02): na
volta seguinte à que ligou o laço, o lado de captura dele é conferido no grafo
(``alto_falante_bt.conferir_o_alvo_do_gravador``). Ligado a outro nó que não o
endpoint do aparelho, o laço cai e aquela rota não se religa — a voz dela nunca
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

CANAIS = 4
MAPA = "[ FL FR RL RR ]"

VOLUME_ABERTO = "100%"
VOLUME_FECHADO = "0%"

_LACOS = Lacos(FAMILIA_DO_LACO_DO_CABO)


def no_de_captura(marca: str) -> str:
    """O ``node.name`` do lado de captura do laço do aparelho desta marca."""
    return f"input.{MARCA_DO_LACO_DO_CABO}{chave_do_aparelho(marca)}"


def chave_do_aparelho(marca: str) -> str:
    """A chave do laço no dono dos laços: a marca do aparelho, em minúsculas."""
    return str(marca).lower()


@dataclass(frozen=True)
class RotaDoCabo:
    """De onde o laço de um aparelho lê e para onde ele toca — os dois por serial."""

    captura: str
    destino: str
    origem: str = ""
    dono: str = ""


def alvo_do_no(nome: str) -> str:
    """O alvo com que o ``pw-loopback`` acerta o nó: o ``object.serial``. "" = não há."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import (
        o_servidor_e_o_pipewire,
        serial_do_no,
    )

    if not nome or not o_servidor_e_o_pipewire():
        return ""
    serial = serial_do_no(nome)
    return "" if serial is None else str(serial)


class HapticaDoCabo:
    """Os laços do cabo, um por DualSense no cabo, pela marca do aparelho.

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
        self._rotas: dict[str, RotaDoCabo] = {}
        self._portao: dict[str, bool] = {}
        self._conferidos: set[str] = set()
        self._recusadas: dict[str, RotaDoCabo] = {}

    def aparelhos(self) -> dict[str, RotaDoCabo]:
        """As marcas com laço pedido, e a rota de cada uma. Leitura."""
        return dict(self._rotas)

    def portao(self, marca: str) -> bool | None:
        """O portão aplicado ao laço do aparelho: aberto, fechado ou ``None`` (não aplicado)."""
        return self._portao.get(marca)

    def casar(self, rotas: Mapping[str, RotaDoCabo], abertos: Iterable[str]) -> None:
        """Os laços ficam os de ``rotas``, e os motores abertos os de ``abertos``."""
        querem_abrir = set(abertos)
        for marca in [n for n in self._rotas if n not in rotas]:
            self.soltar(marca)
        for marca, rota in rotas.items():
            chave = chave_do_aparelho(marca)
            if self._recusadas.get(marca) == rota:
                continue
            self._recusadas.pop(marca, None)
            ja_estava = self._rotas.get(marca) == rota and self._lacos.esta_ligado(chave)
            if ja_estava and marca not in self._conferidos and not self._conferir(marca, rota):
                continue
            if not ja_estava:
                self.soltar(marca)
                if not self._lacos.ligar(
                    chave, captura=rota.captura, destino=rota.destino, canais=CANAIS, mapa=MAPA
                ):
                    logger.info("haptica_do_cabo_laco_nao_subiu", controle=marca)
                    continue
                self._rotas[marca] = rota
                logger.info("haptica_do_cabo_laco_de_pe", controle=marca)
            aberto = marca in querem_abrir
            if self._portao.get(marca) is not aberto and self._aplicar_o_portao(marca, aberto):
                self._portao[marca] = aberto

    def _conferir(self, marca: str, rota: RotaDoCabo) -> bool:
        """O lado de captura do laço está no endpoint do aparelho? ``False`` = caiu."""
        if not rota.origem:
            return True
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            conferir_o_alvo_do_gravador,
        )

        olhar = self._conferir_alvo or conferir_o_alvo_do_gravador
        try:
            ligado = olhar(no_de_captura(marca))
        except Exception as exc:
            logger.debug("haptica_do_cabo_conferencia_falhou", controle=marca, err=str(exc))
            ligado = None
        if ligado is None:
            logger.debug("haptica_do_cabo_nao_conferido", controle=marca)
            return True
        if ligado == rota.origem:
            self._conferidos.add(marca)
            return True
        logger.warning("haptica_do_cabo_ligado_a_outro_no", controle=marca)
        self.soltar(marca)
        self._recusadas[marca] = rota
        return False

    def _aplicar_o_portao(self, marca: str, aberto: bool) -> bool:
        """O volume do fluxo do laço na placa: a frente cheia, os motores pelo portão."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

        correr = self._pactl or rodar_pactl
        no_do_laco = MARCA_DO_LACO_DO_CABO + chave_do_aparelho(marca)
        try:
            if self._indice_do_fluxo is not None:
                indice = self._indice_do_fluxo(no_do_laco)
            else:
                indice = indice_do_fluxo(no_do_laco, rodar_pactl)
            if indice is None:
                return False
            motores = VOLUME_ABERTO if aberto else VOLUME_FECHADO
            resposta = correr([
                "pactl", "set-sink-input-volume", indice,
                VOLUME_ABERTO, VOLUME_ABERTO, motores, motores,
            ])
        except Exception as exc:
            logger.debug("haptica_do_cabo_portao_falhou", controle=marca, err=str(exc))
            return False
        if resposta is None:
            return False
        logger.info("haptica_do_cabo_portao", controle=marca, motores_abertos=aberto)
        return True

    def soltar(self, marca: str) -> None:
        """O laço do aparelho cai. Idempotente — e vem ANTES de o endpoint cair."""
        self._lacos.desligar(chave_do_aparelho(marca))
        if self._rotas.pop(marca, None) is not None:
            logger.info("haptica_do_cabo_laco_solto", controle=marca)
        self._portao.pop(marca, None)
        self._conferidos.discard(marca)

    def parar(self) -> None:
        """Todos os laços caem (o ``stop`` do subsystem)."""
        for marca in list(self._rotas):
            self.soltar(marca)


__all__ = [
    "CANAIS",
    "MAPA",
    "VOLUME_ABERTO",
    "VOLUME_FECHADO",
    "HapticaDoCabo",
    "RotaDoCabo",
    "alvo_do_no",
    "chave_do_aparelho",
    "no_de_captura",
]
