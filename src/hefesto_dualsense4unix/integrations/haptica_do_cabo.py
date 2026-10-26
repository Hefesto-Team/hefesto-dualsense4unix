"""A háptica do cabo passa pelo endpoint do aparelho — A-HAPTICA-E-POR-APARELHO-01.

O jogo toca no endpoint do APARELHO (um por DualSense), e este módulo o leva à placa do
controle: UM laço por controle no cabo, do monitor do endpoint à placa, nos quatro canais
(``integrations/laco_de_audio.Lacos``). Não há portão de quem mexeu: os traseiros (os motores)
levam o ganho do controle, ``1.0000 1.0000 G G``, e a frente passa cheia. O alvo do laço é o
``object.serial`` (:func:`alvo_do_no`), nunca o nome; a história está em
``docs/research/o-porque-dos-modulos.md``, seção ``haptica_do_cabo``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
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

#: Os quatro canais do fluxo do laço vão em FATOR LINEAR, e nunca em ``%``: os
#: motores levam o ganho em fator, e o ``pactl`` recusa o comando que mistura as
#: duas unidades (``Inconsistent volume specification.``, antes de falar com o
#: servidor). Com a frente em ``100%`` o volume só fechava: do ``d61af1907``
#: (14/10, 12h51) à rodada 1 da bancada, nenhum motor do laço abriu no cabo.
VOLUME_ABERTO = "1.0000"

_LACOS = Lacos(FAMILIA_DO_LACO_DO_CABO)


def volume_dos_motores(ganho: float) -> str:
    """O volume dos traseiros do fluxo do laço: o ganho linear do controle."""
    return f"{max(float(ganho), 0.0):.4f}"


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
    que se guarda aqui é só o que cada laço foi pedido para ligar e o volume
    que já se aplicou — para não reescrevê-lo a cada volta.
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
        self._motores: dict[str, str] = {}
        self._conferidos: set[str] = set()
        self._recusadas: dict[str, RotaDoCabo] = {}
        self._falhas: dict[str, tuple[str, str]] = {}

    def aparelhos(self) -> dict[str, RotaDoCabo]:
        """As marcas com laço pedido, e a rota de cada uma. Leitura."""
        return dict(self._rotas)

    def volume_aplicado(self, marca: str) -> bool:
        """O volume dos motores já foi aplicado ao laço do aparelho?"""
        return marca in self._motores

    def casar(
        self,
        rotas: Mapping[str, RotaDoCabo],
        ganhos: Mapping[str, float] | None = None,
    ) -> None:
        """Os laços ficam os de ``rotas``, e os motores de cada um vão no ganho da marca.

        ``ganhos`` é o fator linear da háptica de cada marca (o ``GANHO`` do dono
        dela); sem ele, os motores vão a 1,0.
        """
        ganho_de = dict(ganhos or {})
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
            motores = volume_dos_motores(ganho_de.get(marca, 1.0))
            if self._motores.get(marca) != motores and self._aplicar_o_volume(
                marca, motores, dono=rota.dono
            ):
                self._motores[marca] = motores

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

    def _aplicar_o_volume(self, marca: str, motores: str, *, dono: str = "") -> bool:
        """O volume do fluxo do laço na placa: a frente cheia, os motores pelo ganho.

        É o único lugar do cabo onde mora o ganho da háptica (OS-QUATRO-EM-HARMONIA-01,
        item 1): o volume por canal de um FLUXO é do conversor dele, e não do nó ALSA.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

        correr = self._pactl or rodar_pactl
        no_do_laco = MARCA_DO_LACO_DO_CABO + chave_do_aparelho(marca)
        try:
            if self._indice_do_fluxo is not None:
                indice = self._indice_do_fluxo(no_do_laco)
            else:
                indice = indice_do_fluxo(no_do_laco, rodar_pactl)
            if indice is None:
                return self._dizer_a_falha(marca, dono, "sem_fluxo_do_laco", motores)
            resposta = correr([
                "pactl", "set-sink-input-volume", indice,
                VOLUME_ABERTO, VOLUME_ABERTO, motores, motores,
            ])
        except Exception as exc:
            return self._dizer_a_falha(marca, dono, f"erro: {exc}", motores)
        if resposta is None:
            return self._dizer_a_falha(marca, dono, "pactl_recusou", motores)
        self._falhas.pop(marca, None)
        logger.info(
            "haptica_do_cabo_portao",
            controle=marca,
            uniq=dono,
            motores=motores,
        )
        return True

    def _dizer_a_falha(self, marca: str, dono: str, motivo: str, motores: str) -> bool:
        """O volume que não se aplicou deixa rastro em ``info``, uma linha por mudança.

        A volta tenta de novo a cada passada; sem esta linha, o volume preso
        em zero (o de 14/10) não aparecia no diário.
        """
        if self._falhas.get(marca) != (motivo, motores):
            self._falhas[marca] = (motivo, motores)
            logger.info(
                "haptica_do_cabo_portao_falhou",
                controle=marca,
                uniq=dono,
                motivo=motivo,
                motores=motores,
            )
        return False

    def soltar(self, marca: str) -> None:
        """O laço do aparelho cai. Idempotente — e vem ANTES de o endpoint cair."""
        self._lacos.desligar(chave_do_aparelho(marca))
        self._falhas.pop(marca, None)
        if self._rotas.pop(marca, None) is not None:
            logger.info("haptica_do_cabo_laco_solto", controle=marca)
        self._motores.pop(marca, None)
        self._conferidos.discard(marca)

    def parar(self) -> None:
        """Todos os laços caem (o ``stop`` do subsystem)."""
        for marca in list(self._rotas):
            self.soltar(marca)


__all__ = [
    "CANAIS",
    "MAPA",
    "VOLUME_ABERTO",
    "HapticaDoCabo",
    "RotaDoCabo",
    "alvo_do_no",
    "chave_do_aparelho",
    "no_de_captura",
    "volume_dos_motores",
]
