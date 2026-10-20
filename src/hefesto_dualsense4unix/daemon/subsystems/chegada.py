"""A Chegada e a Assinatura: o aperto de mão de cada controle ao entrar na mesa (20/10/2026).

Ao conectar, a barra sobe na cor do controle, a háptica dá um Toque e o gatilho clica uma vez. O
Toque tem a nota da unidade, pela cor do plástico e nunca pelo número do jogador: Starlight Blue
150 Hz, White 165, Cosmic Red 180, Galactic Purple 195. Espera a rajada da Steam passar (um gatilho
de fim de sequência, como o da lightbar), cede ao que o jogo já escreveu e vale em todo estilo,
menos o Nativo e o Personalizado, no cabo e no rádio.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.profiles import formas_de_haptica
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

RGB = tuple[int, int, int]

#: O nome do gatilho no registro do daemon.
NOME_DO_GATILHO = "chegada"

#: Quanto a mesa sossega antes da Chegada: a rajada da Steam dura ~3,9 s (ensaio
#: ``btmon-a-rajada-tem-hora``), e o gatilho da lightbar fecha a sequência 1,6 a 2,9 s depois da
#: conexão (diário do daemon de 19/10/2026).
ESPERA_S = 4.0

#: A nota de cada unidade, pela cor do plástico (o ``id`` da linha de ``cores-do-dualsense.csv``).
NOTA_DA_COR: dict[str, int] = {
    "starlight-blue": 150,
    "white": 165,
    "cosmic-red": 180,
    "galactic-purple": 195,
}

#: O Toque da Chegada: a energia e o tamanho (o Toque do tiro tem de 25 a 60 ms).
ENERGIA_DO_TOQUE = 0.9
DURACAO_DO_TOQUE_MS = 120
#: A subida da barra: de um quinto à cor cheia em cinco quadros (uma subida, nunca um lampejo).
BRILHOS_DA_SUBIDA: tuple[float, ...] = (0.2, 0.4, 0.6, 0.8, 1.0)
PASSO_DA_SUBIDA_S = 0.12
#: O clique do gatilho dura o primeiro passo da subida e sai.
QUADROS_DO_CLIQUE = 1


@dataclass
class PontasDaChegada:
    """Tudo o que a Chegada pergunta ou escreve, injetado (e por isso testável)."""

    pode: Callable[[], bool]
    conectados: Callable[[], frozenset[str]]
    jogo_escreve: Callable[[str, str], bool]
    nota: Callable[[str], int | None]
    cor: Callable[[str], RGB | None]
    pintar: Callable[[str, RGB], object]
    devolver_a_luz: Callable[[], object]
    tocar: Callable[[str, float, str, int, str], object]
    clicar: Callable[[str], object]
    soltar_o_clique: Callable[[str], object]
    dormir: Callable[[float], None] = time.sleep


def a_chegada_vale(estilo: str | None, modo_nativo: bool) -> bool:
    """Todo estilo vale, menos o Nativo e o Personalizado; nunca no Modo Nativo.

    Sem estilo (o perfil não escolheu nenhum) é como o Personalizado: a mão da pessoa manda.
    """
    from hefesto_dualsense4unix.profiles.estilos_de_jogo import SEM_COR

    return bool(estilo) and estilo not in SEM_COR and not modo_nativo


def nota_da_unidade(daemon: Any, uniq: str) -> int | None:
    """A nota (Hz) da cor do plástico de ``uniq``; ``None`` quando a fábrica ainda não disse.

    A nota é da UNIDADE: vem da identidade de fábrica, nunca da posição nem do número de jogador.
    """
    registro = getattr(daemon, "identity_registry", None)
    ler = getattr(registro, "identidade_de_fabrica", None)
    if not callable(ler):
        return None
    cor = getattr(ler(uniq), "cor", None)
    return NOTA_DA_COR.get(str(getattr(cor, "id", "") or ""))


class Chegada:
    """Os controles que chegaram desde a última Chegada, e o aperto de mão deles."""

    def __init__(self, pontas: PontasDaChegada) -> None:
        self._pontas = pontas
        self._pendentes: dict[str, None] = {}

    @property
    def pendentes(self) -> tuple[str, ...]:
        return tuple(self._pendentes)

    def chegou(self, uniq: str) -> None:
        """Um controle novo na mesa: a Chegada dele fica devida (uma por conexão)."""
        if uniq:
            self._pendentes[uniq] = None

    def esquecer(self) -> None:
        self._pendentes.clear()

    def tocar(self) -> dict[str, dict[str, bool]]:
        """A Chegada de todo controle pendente que ainda está na mesa. Devolve o que escreveu."""
        pendentes, self._pendentes = tuple(self._pendentes), {}
        if not pendentes or not self._pontas.pode():
            return {}
        na_mesa = self._pontas.conectados()
        quem = [u for u in pendentes if u in na_mesa]
        feito: dict[str, dict[str, bool]] = {}
        luz: dict[str, RGB] = {}
        for uniq in quem:
            livre_luz = not self._pontas.jogo_escreve(uniq, "luz")
            livre_gatilho = not self._pontas.jogo_escreve(uniq, "gatilho")
            cor = self._pontas.cor(uniq) if livre_luz else None
            feito[uniq] = {"luz": cor is not None, "toque": False, "gatilho": livre_gatilho}
            if cor is not None:
                luz[uniq] = cor
            forma = formas_de_haptica.forma_da_nota(self._pontas.nota(uniq))
            feito[uniq]["toque"] = bool(
                self._pontas.tocar(uniq, ENERGIA_DO_TOQUE, "centro", DURACAO_DO_TOQUE_MS, forma))
            if livre_gatilho:
                self._pontas.clicar(uniq)
        self._subir_a_luz(luz)
        for uniq, canais in feito.items():
            if canais["gatilho"]:
                self._pontas.soltar_o_clique(uniq)
        logger.info("chegada_tocada", controles=len(feito))
        return feito

    def _subir_a_luz(self, luz: dict[str, RGB]) -> None:
        """A barra sobe até a cor cheia em todos de uma vez, e o backend a devolve ao desejado."""
        if not luz:
            return
        for brilho in BRILHOS_DA_SUBIDA:
            for uniq, (r, g, b) in luz.items():
                self._pontas.pintar(uniq, (int(r * brilho), int(g * brilho), int(b * brilho)))
            self._pontas.dormir(PASSO_DA_SUBIDA_S)
        self._pontas.devolver_a_luz()


def pontas_de_producao(daemon: Any) -> PontasDaChegada:
    """As pontas do daemon vivo: o estilo, a mesa, o jogo, a cor, o Toque e o gatilho."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_animada import escritor_de_producao
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import bloco_do_clique, estilo_ativo
    controller = getattr(daemon, "controller", None)
    escrever_a_luz, devolver = escritor_de_producao(daemon)

    def pode() -> bool:
        return a_chegada_vale(estilo_ativo(daemon), bool(daemon.is_native_mode()))

    def conectados() -> frozenset[str]:
        alvos = getattr(controller, "alvos_conectados", None)
        return frozenset(u for u in alvos().values() if u) if callable(alvos) else frozenset()

    def jogo_escreve(uniq: str, canal: str) -> bool:
        from hefesto_dualsense4unix.mods.porta import o_jogo_escreve_no_servico

        return bool(o_jogo_escreve_no_servico(daemon)(uniq, canal))

    def cor(uniq: str) -> RGB | None:
        ler = getattr(controller, "resolved_led_for", None)
        achada = ler(uniq) if callable(ler) else None
        if not isinstance(achada, tuple) or len(achada) != 3:
            return None
        return (int(achada[0]), int(achada[1]), int(achada[2]))

    def tocar(uniq: str, energia: float, lado: str, duracao_ms: int, forma: str) -> object:
        alto_falante = getattr(daemon, "_alto_falante_subsystem", None)
        tocar_o_toque = getattr(alto_falante, "tocar_o_toque", None)
        if not callable(tocar_o_toque):
            return False
        if forma == formas_de_haptica.TOQUE:
            return tocar_o_toque(uniq, energia, lado, duracao_ms)
        return tocar_o_toque(uniq, energia, lado, duracao_ms, forma)

    bloco = bloco_do_clique()

    def clicar(uniq: str) -> object:
        escrever = getattr(controller, "set_game_trigger_for", None)
        return escrever(uniq, "right", bloco) if callable(escrever) else False

    def soltar_o_clique(uniq: str) -> object:
        soltar = getattr(controller, "soltar_o_gatilho_do_jogo_for", None)
        return soltar(uniq, "right", bloco) if callable(soltar) else False

    return PontasDaChegada(
        pode, conectados, jogo_escreve, lambda uniq: nota_da_unidade(daemon, uniq), cor,
        escrever_a_luz, lambda: devolver(""), tocar, clicar, soltar_o_clique)


def chegada_de(daemon: Any) -> Chegada:
    """A :class:`Chegada` DESTE daemon, criada na primeira consulta."""
    achada = getattr(daemon, "_chegada", None)
    if isinstance(achada, Chegada):
        return achada
    achada = Chegada(pontas_de_producao(daemon))
    try:
        daemon._chegada = achada
    except Exception:
        logger.debug("chegada_sem_onde_morar", exc_info=True)
    return achada


__all__ = [
    "BRILHOS_DA_SUBIDA",
    "ESPERA_S",
    "NOME_DO_GATILHO",
    "NOTA_DA_COR",
    "Chegada",
    "PontasDaChegada",
    "a_chegada_vale",
    "chegada_de",
    "nota_da_unidade",
    "pontas_de_producao",
]
