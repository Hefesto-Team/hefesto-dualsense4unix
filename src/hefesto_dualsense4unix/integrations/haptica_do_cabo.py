"""A háptica do cabo passa pelo endpoint do aparelho — A-HAPTICA-E-POR-APARELHO-01.

O jogo toca no endpoint do APARELHO (um por DualSense), e este módulo o leva à placa do
controle: UM laço por controle no cabo, do monitor do endpoint à placa, nos quatro canais
(``integrations/laco_de_audio.Lacos``). Não há portão de quem mexeu: os traseiros (os motores)
levam o ganho do controle, ``1.0000 1.0000 G G``, e a frente passa cheia. O ganho se confirma
pela leitura do fluxo, nunca pelo ``rc``: o servidor restaura no laço que nasce o último volume
guardado para o nome dele (``module-stream-restore``). O alvo do laço é o ``object.serial``
(:func:`alvo_do_no`), nunca o nome; a história está em ``docs/research/o-porque-dos-modulos.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations.audio_ks_dualsense import (
    FAMILIA_DO_LACO_DO_CABO,
    MARCA_DO_LACO_DO_CABO,
)
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos
from hefesto_dualsense4unix.integrations.porta_do_som import lista_do_json
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

CANAIS = 4
MAPA = "[ FL FR RL RR ]"

VOLUME_ABERTO = "1.0000"

CANAIS_DOS_MOTORES = ("rear-left", "rear-right")

VOLUME_NORMAL = 65536

FOLGA_DO_VOLUME = 64

_LACOS = Lacos(FAMILIA_DO_LACO_DO_CABO)


def volume_dos_motores(ganho: float) -> str:
    """O volume dos traseiros do fluxo do laço: o ganho linear do controle."""
    return f"{max(float(ganho), 0.0):.4f}"


def bruto_do_fator(fator: float) -> int:
    """O volume bruto que o ``pactl`` manda por um fator linear (a raiz cúbica do fator)."""
    return 0 if fator <= 0 else round(float(fator) ** (1 / 3) * VOLUME_NORMAL)


def os_motores_estao_em(lidos: tuple[int, ...] | None, motores: str) -> bool:
    """Os motores lidos no fluxo são os do fator ``motores``? Sem leitura, não estão."""
    if not lidos:
        return False
    alvo = bruto_do_fator(float(motores))
    return all(abs(v - alvo) <= FOLGA_DO_VOLUME for v in lidos)


@dataclass(frozen=True)
class FluxoDoLaco:
    """O fluxo do laço no servidor: o índice e o volume bruto dos motores (``None``, não sei)."""

    indice: str
    motores: tuple[int, ...] | None = None


def _motores_do_volume(volume: object) -> tuple[int, ...] | None:
    if not isinstance(volume, Mapping):
        return None
    lidos: list[int] = []
    for canal in CANAIS_DOS_MOTORES:
        dado = volume.get(canal)
        valor = dado.get("value") if isinstance(dado, Mapping) else None
        if not isinstance(valor, int) or isinstance(valor, bool):
            return None
        lidos.append(valor)
    return tuple(lidos)


def ler_o_fluxo_do_laco(
    no_do_laco: str, correr: Callable[[list[str]], str | None] | None = None
) -> FluxoDoLaco | None:
    """O fluxo que carrega ``no_do_laco``, pelo JSON do ``pactl``. ``None`` = não há.

    Sem ``correr``, a pergunta vai pelo executor do som (:func:`alto_falante_bt.rodar_pactl`),
    que responde pelo retrato do servidor quando ele está vivo, como todo outro leitor.
    """
    from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

    ler = correr if correr is not None else rodar_pactl
    objetos = lista_do_json(ler(["pactl", "--format=json", "list", "sink-inputs"]))
    for o in objetos or ():
        indice = o.get("index")
        props = o.get("properties")
        if not isinstance(indice, int) or isinstance(indice, bool):
            continue
        if not isinstance(props, Mapping) or not any(no_do_laco in str(v) for v in props.values()):
            continue
        return FluxoDoLaco(str(indice), _motores_do_volume(o.get("volume")))
    return None


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
        ler_o_fluxo: Callable[[str], FluxoDoLaco | None] | None = None,
    ) -> None:
        self._lacos: Any = lacos if lacos is not None else _LACOS
        self._indice_do_fluxo = indice_do_fluxo
        self._ler_o_fluxo_injetado = ler_o_fluxo
        self._pactl = pactl
        self._conferir_alvo = conferir
        self._rotas: dict[str, RotaDoCabo] = {}
        self._motores: dict[str, str] = {}
        self._conferidos: set[str] = set()
        self._recusadas: dict[str, RotaDoCabo] = {}
        self._falhas: dict[str, tuple[str, str]] = {}
        self._ganho_dito: set[str] = set()

    def aparelhos(self) -> dict[str, RotaDoCabo]:
        """As marcas com laço pedido, e a rota de cada uma. Leitura."""
        return dict(self._rotas)

    def leva_os_motores(self, marca: str) -> bool:
        """O volume dos motores se aplicou ao laço e é maior que 0 (com 0 a háptica não chega)."""
        try:
            return float(self._motores.get(marca, "0")) > 0
        except ValueError:
            return False

    def casar(
        self,
        rotas: Mapping[str, RotaDoCabo],
        ganhos: Mapping[str, float] | None = None,
    ) -> None:
        """Os laços ficam os de ``rotas``, e os motores de cada um vão no ganho da marca.

        ``ganhos`` é o fator linear da háptica de cada marca (o ``GANHO`` do dono
        da marca); sem ele, os motores vão a 1,0.
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
            if self._motores.get(marca) == motores and self._seguem_no_fluxo(marca, motores):
                continue
            self._motores.pop(marca, None)
            if self._aplicar_o_volume(marca, motores, dono=rota.dono, recem_ligado=not ja_estava):
                self._motores[marca] = motores

    def _no_do_laco(self, marca: str) -> str:
        return MARCA_DO_LACO_DO_CABO + chave_do_aparelho(marca)

    def _ler_o_fluxo(self, marca: str) -> FluxoDoLaco | None:
        """O fluxo do laço desta marca, com os motores lidos quando o servidor os diz."""
        no_do_laco = self._no_do_laco(marca)
        if self._ler_o_fluxo_injetado is not None:
            return self._ler_o_fluxo_injetado(no_do_laco)
        if self._indice_do_fluxo is not None:
            indice = self._indice_do_fluxo(no_do_laco)
            return None if indice is None else FluxoDoLaco(indice)
        return ler_o_fluxo_do_laco(no_do_laco, self._pactl)

    def _seguem_no_fluxo(self, marca: str, motores: str) -> bool:
        """Os motores aplicados seguem no fluxo? Só a leitura de outro valor diz que não."""
        try:
            fluxo = self._ler_o_fluxo(marca)
        except Exception as exc:
            logger.debug("haptica_do_cabo_leitura_falhou", controle=marca, err=str(exc))
            return True
        if fluxo is None or fluxo.motores is None or os_motores_estao_em(fluxo.motores, motores):
            return True
        logger.info("haptica_do_cabo_motores_mudaram_no_fluxo", controle=marca, motores=motores)
        return False

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

    def _aplicar_o_volume(
        self, marca: str, motores: str, *, dono: str = "", recem_ligado: bool = False
    ) -> bool:
        """O volume do fluxo do laço na placa: a frente cheia, os motores pelo ganho.

        É o único lugar do cabo onde mora o ganho da háptica (OS-QUATRO-EM-HARMONIA-01,
        item 1): o volume por canal de um FLUXO é do conversor dele, e não do nó ALSA.
        Aplicado é o que a leitura do fluxo mostra: o que já nasceu no ganho não se
        reescreve, e a escrita que o ``pactl`` aceita sem aplicar não conta. Na passada
        em que o laço acabou de subir, o fluxo ainda não existe: espera, sem falha.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

        correr = self._pactl or rodar_pactl
        try:
            fluxo = self._ler_o_fluxo(marca)
            if fluxo is None:
                return self._dizer_a_falha(
                    marca, dono, "sem_fluxo_do_laco", motores, recem_ligado=recem_ligado)
            if not os_motores_estao_em(fluxo.motores, motores):
                resposta = correr([
                    "pactl", "set-sink-input-volume", fluxo.indice,
                    VOLUME_ABERTO, VOLUME_ABERTO, motores, motores,
                ])
                if resposta is None:
                    return self._dizer_a_falha(
                        marca, dono, "pactl_recusou", motores, recem_ligado=recem_ligado)
                lido = self._ler_o_fluxo(marca)
                if lido is not None and lido.motores is not None and not os_motores_estao_em(
                    lido.motores, motores
                ):
                    return self._dizer_a_falha(marca, dono, "fluxo_nao_confirmou", motores)
        except Exception as exc:
            return self._dizer_a_falha(marca, dono, f"erro: {exc}", motores)
        self._falhas.pop(marca, None)
        dizer = logger.debug if marca in self._ganho_dito else logger.info
        self._ganho_dito.add(marca)
        dizer("haptica_do_cabo_portao", controle=marca, uniq=dono, motores=motores)
        return True

    def _dizer_a_falha(
        self, marca: str, dono: str, motivo: str, motores: str, *, recem_ligado: bool = False
    ) -> bool:
        """O volume que não se aplicou deixa rastro em ``info``, uma linha por mudança.

        A volta tenta de novo a cada passada; sem esta linha, o volume preso
        em zero (o de 14/10) não aparecia no diário. O laço que acabou de subir
        ainda não tem fluxo (ou o retrato mostra o do laço que acabou de cair):
        isso é espera, em ``debug``.
        """
        if recem_ligado:
            logger.debug("haptica_do_cabo_espera_o_fluxo", controle=marca, motivo=motivo)
            return False
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
        self._ganho_dito.discard(marca)

    def parar(self) -> None:
        """Todos os laços caem (o ``stop`` do subsystem)."""
        for marca in list(self._rotas):
            self.soltar(marca)


__all__ = [
    "CANAIS",
    "CANAIS_DOS_MOTORES",
    "MAPA",
    "VOLUME_ABERTO",
    "FluxoDoLaco",
    "HapticaDoCabo",
    "RotaDoCabo",
    "alvo_do_no",
    "bruto_do_fator",
    "chave_do_aparelho",
    "ler_o_fluxo_do_laco",
    "no_de_captura",
    "os_motores_estao_em",
    "volume_dos_motores",
]
