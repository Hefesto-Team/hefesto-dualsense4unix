"""A barra de luz que se anima sozinha (A-ABA-ILUMINACAO-DO-TODO-01).

O perfil guarda o efeito de cada controle em ``leds.efeito`` (``base;cores;ritmo``); ``None`` é a
luz fixa e este laço não escreve nada. Quem manda na barra, em ordem: o jogo (cala quando ele
pinta, pela política do tato vivo), o Modo Nativo, o Automático da aba, o brilho zero e a «Bateria
longa» (a barra fica fixa na cor do perfil). No máximo 30 quadros por segundo por controle e quadro
igual ao anterior não sai; o desenho de cada efeito no tempo é de ``profiles/efeitos_de_luz`` e o
«Sem piscar» da mesa é lido a cada tique. O quadro pinta a barra sem entrar no estado desejado;
ao sair, a barra volta a ele. Enquanto o pulso do tiro do tato vivo segura a barra, o efeito espera.
O porquê de cada escolha: docs/research/o-porque-dos-modulos.md, seção «luz_animada».
"""
from __future__ import annotations

import asyncio
import dataclasses
import time
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
    CANAL_LUZ,
    controles_do_daemon,
    decidir,
    estado_do_controle,
    ha_jogo,
    motor_do,
)
from hefesto_dualsense4unix.profiles.efeitos_de_luz import (
    BASES_DO_RELOGIO_COMUM,
    TETO_DO_PISCAR_HZ,
    amplitude_da_mare,
    cor_no_instante,
    frequencia_do_piscar_hz,
    periodo_do_arco_iris_s,
    periodo_do_respirar_s,
)
from hefesto_dualsense4unix.profiles.schema import (
    EfeitoDaLuz,
    LedsConfig,
    Profile,
    controles_em_economia,
    economia_da_mesa,
    economia_vale,
    ler_o_efeito_da_luz,
    sem_piscar_da_mesa,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

RGB = tuple[int, int, int]

#: O teto de quadros por segundo de cada controle.
QUADROS_POR_SEGUNDO_MAXIMO = 30
INTERVALO_MINIMO = 1.0 / QUADROS_POR_SEGUNDO_MAXIMO
#: O laço dorme isto entre um tique e outro (o ``INTERVALO_MINIMO`` é quem corta o excesso).
INTERVALO_DO_LACO_S = INTERVALO_MINIMO
#: De quanto em quanto tempo o laço relê o perfil ativo (só o arquivo, sem semear).
RELEITURA_DO_PLANO_S = 0.5


@dataclass(frozen=True)
class PlanoDoControle:
    """O que o perfil manda tocar num controle: o efeito, o brilho da barra, o lugar e a semente.

    ``posicao`` é o lugar do controle na mesa (0 a 3): o arco-íris defasa um quarto de volta por
    lugar. ``semente`` é do controle (do endereço dele): a chama passeia por ela. ``amplitude``
    é a fração dos 30 graus que a Maré pode andar sem aproximar este controle dos outros.
    """

    efeito: EfeitoDaLuz
    brilho: float
    posicao: int = 0
    semente: int = 0
    amplitude: float = 1.0


def _semente_do_controle(uniq: str) -> int:
    """Um número estável por controle (o ``hash`` do Python muda a cada processo)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return zlib.crc32((norm_mac(uniq) or uniq).encode())


def _leds_do_controle(perfil: Profile, uniq: str) -> tuple[LedsConfig | None, set[str]]:
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    chave = norm_mac(uniq)
    dele = (perfil.controllers or {}).get(chave) if chave else None
    leds = getattr(dele, "leds", None)
    return leds, set(leds.model_fields_set) if leds is not None else set()


def _em_economia(
    uniq: str, mesa: bool, em_economia: frozenset[str]
) -> bool:
    """A economia vale neste controle? A mesma regra que põe a economia na vista do perfil."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return economia_vale(norm_mac(uniq) in em_economia, mesa)


def plano_do_perfil(
    perfil: Profile,
    uniqs: list[str],
    *,
    mesa_em_economia: bool | None = None,
    em_economia: frozenset[str] | None = None,
) -> dict[str, PlanoDoControle]:
    """O plano de cada controle em ``uniqs``; quem não tem efeito (ou não pode tê-lo) fica de fora.

    O efeito do controle vale se ele o escreveu (``efeito`` nos campos dele, inclusive ``None`` =
    luz fixa explícita); senão herda o global. O brilho segue a regra de
    ``profiles.manager._controllers_to_specs``: o do controle se ele o escreveu, senão o global.
    Na economia «Bateria longa» (da mesa inteira ou do controle, a mesma ``economia_vale`` da
    vista que vai ao aparelho) o controle fica de fora: a barra segue fixa na cor do perfil, e ao
    sair da economia o plano o devolve. Sem a economia na mão, lê a declaração viva.
    """
    if perfil.leds.modo == "automatico":  # (noqa-acento) chave do contrato
        return {}
    mesa = economia_da_mesa() if mesa_em_economia is None else bool(mesa_em_economia)
    ligados = controles_em_economia() if em_economia is None else em_economia
    fora: dict[str, PlanoDoControle] = {}
    for posicao, uniq in enumerate(uniqs):
        if _em_economia(uniq, mesa, ligados):
            continue
        leds, campos = _leds_do_controle(perfil, uniq)
        texto = leds.efeito if leds is not None and "efeito" in campos else perfil.leds.efeito
        efeito = ler_o_efeito_da_luz(texto)
        if efeito is None:
            continue
        brilho = (
            leds.lightbar_brightness
            if leds is not None and "lightbar_brightness" in campos
            else perfil.leds.lightbar_brightness
        )
        if float(brilho) <= 0.0:
            continue
        fora[uniq] = PlanoDoControle(
            efeito, float(brilho), posicao % 4, _semente_do_controle(uniq)
        )
    return _com_a_amplitude_da_mare(fora)


def _com_a_amplitude_da_mare(plano: dict[str, PlanoDoControle]) -> dict[str, PlanoDoControle]:
    """Dá a cada controle em Maré a amplitude que o mantém longe dos outros em Maré."""
    mares = {u: p for u, p in plano.items() if p.efeito.base == "mare"}
    if len(mares) < 2:
        return plano
    bases = [(p.efeito.cores or ((255, 255, 255),))[0] for p in mares.values()]
    amplitude = amplitude_da_mare(bases)
    return {
        u: dataclasses.replace(p, amplitude=amplitude) if u in mares else p
        for u, p in plano.items()
    }


def cor_com_o_brilho(cor: RGB, brilho: float) -> RGB:
    """A cor no brilho do perfil, pela MESMA função da cor fixa."""
    from hefesto_dualsense4unix.core.led_control import LedSettings

    ajustada = LedSettings(lightbar=cor, brightness_level=float(brilho)).apply_brightness(
        float(brilho)
    ).lightbar
    r, g, b = ajustada
    return (int(r), int(g), int(b))


class LuzAnimada:
    """O tique do efeito, com tudo o que fala com o mundo injetado (e por isso testável)."""

    def __init__(
        self,
        escrever: Callable[[str, RGB], object],
        soltar: Callable[[str], object],
        *,
        intervalo_minimo: float = INTERVALO_MINIMO,
        sem_piscar: Callable[[], bool] = sem_piscar_da_mesa,
    ) -> None:
        self._escrever = escrever
        self._soltar = soltar
        self._sem_piscar = sem_piscar
        self._intervalo = max(intervalo_minimo, INTERVALO_MINIMO)
        self._ultimo_quadro: dict[str, RGB] = {}
        self._escrito_em: dict[str, float] = {}
        self._inicio: dict[str, float] = {}
        #: O relógio da mesa: nasce com o primeiro controle que toca e morre com o último. O
        #: arco-íris e a Maré contam por ele, senão quem entrou depois desfaz a defasagem.
        self._origem: float | None = None

    @property
    def tocando(self) -> frozenset[str]:
        return frozenset(self._inicio)

    def tique(
        self,
        agora: float,
        plano: Mapping[str, PlanoDoControle],
        calados: frozenset[str] = frozenset(),
        pausados: frozenset[str] = frozenset(),
    ) -> int:
        """Escreve o quadro de cada controle que toca; devolve quantos quadros saíram.

        ``calados`` param e devolvem a barra; ``pausados`` só deixam de escrever (outro dono a
        segura por um instante) e, na volta, o primeiro quadro sai mesmo igual ao último.
        """
        for uniq in [u for u in self._inicio if u not in plano or u in calados]:
            self.parar(uniq)
        escritos = 0
        sem_piscar = bool(self._sem_piscar())
        for uniq, dele in plano.items():
            if uniq in calados:
                continue
            if uniq in pausados:
                self._ultimo_quadro.pop(uniq, None)
                continue
            if agora - self._escrito_em.get(uniq, float("-inf")) < self._intervalo:
                continue
            inicio = self._inicio.setdefault(uniq, agora)
            if self._origem is None:
                self._origem = inicio
            if dele.efeito.base in BASES_DO_RELOGIO_COMUM:
                inicio = self._origem
            cor = cor_no_instante(
                dele.efeito, agora - inicio, dele.posicao, dele.semente, sem_piscar, dele.amplitude
            )
            quadro = cor_com_o_brilho(cor, dele.brilho)
            self._escrito_em[uniq] = agora
            if self._ultimo_quadro.get(uniq) == quadro:
                continue
            self._ultimo_quadro[uniq] = quadro
            self._escrever(uniq, quadro)
            escritos += 1
        return escritos

    def repintar(self) -> None:
        """Esquece o último quadro de todos: o corrente sai no próximo tique, mesmo igual.

        Quem repintou a barra por fora (a cor base do perfil) a deixou diferente do que este laço
        acha que está lá; sem isto a cor base ficaria até o primeiro quadro DIFERENTE do efeito.
        """
        self._ultimo_quadro.clear()

    def parar(self, uniq: str) -> None:
        """Devolve a barra de ``uniq`` ao perfil, uma vez; sem efeito tocando, não faz nada."""
        if self._inicio.pop(uniq, None) is None:
            return
        self._ultimo_quadro.pop(uniq, None)
        self._escrito_em.pop(uniq, None)
        if not self._inicio:
            self._origem = None
        self._soltar(uniq)

    def parar_tudo(self) -> None:
        for uniq in list(self._inicio):
            self.parar(uniq)


def escritor_de_producao(
    daemon: Any,
) -> tuple[Callable[[str, RGB], object], Callable[[str], object]]:
    """As duas pontas do backend: pintar o quadro sem lembrá-lo e devolver a barra ao desejado."""
    controller = getattr(daemon, "controller", None)

    def escrever(uniq: str, cor: RGB) -> object:
        pintar = getattr(controller, "pintar_a_barra_sem_lembrar", None)
        return pintar(uniq, cor) if callable(pintar) else False

    def soltar(uniq: str) -> object:
        repintar = getattr(controller, "reassert_resolved_outputs", None)
        return repintar() if callable(repintar) else None

    return escrever, soltar


def perfil_ativo(daemon: Any) -> Profile | None:
    """O perfil ativo como vale neste computador, lido do arquivo (sem semear nem varrer)."""
    nome = getattr(getattr(daemon, "store", None), "active_profile", None)
    if not isinstance(nome, str) or not nome:
        return None
    try:
        from hefesto_dualsense4unix.profiles.loader import perfil_em_disco
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale

        perfil = perfil_em_disco(nome)
        return None if perfil is None else o_que_vale(perfil)
    except Exception:
        logger.debug("luz_animada_perfil_ilegivel", exc_info=True)
        return None


class Passo:
    """Um tique do laço de produção, separado para se testar com relógio injetado."""

    def __init__(self, daemon: Any, luz: LuzAnimada) -> None:
        self.daemon = daemon
        self.luz = luz
        self._plano: dict[str, PlanoDoControle] = {}
        self._lido_em = float("-inf")
        self._repinturas: int | None = None

    def _houve_repintura_de_fora(self) -> bool:
        """O backend repintou a luz resolvida desde o último tique? (o contador dele subiu)."""
        contador = getattr(getattr(self.daemon, "controller", None), "repinturas_da_luz", None)
        if not isinstance(contador, int):
            return False
        subiu = self._repinturas is not None and contador != self._repinturas
        self._repinturas = contador
        return subiu

    def __call__(self, agora: float) -> int:
        controles = controles_do_daemon(self.daemon)
        if self._houve_repintura_de_fora():
            self.luz.repintar()
        if agora - self._lido_em >= RELEITURA_DO_PLANO_S:
            self._lido_em = agora
            perfil = perfil_ativo(self.daemon)
            self._plano = (
                {} if perfil is None else plano_do_perfil(perfil, [c.uniq for c in controles])
            )
        if not self._plano:
            self.luz.parar_tudo()
            return 0
        plano = {c.uniq: self._plano[c.uniq] for c in controles if c.uniq in self._plano}
        jogo = ha_jogo(self.daemon)
        calados = frozenset(
            c.uniq
            for c in controles
            if c.uniq in plano and not self._o_hefesto_pode_pintar(c, jogo)
        )
        return self.luz.tique(agora, plano, calados, self._o_pulso_do_tiro_segura())

    def _o_pulso_do_tiro_segura(self) -> frozenset[str]:
        """Os controles em que o pulso do tiro do tato vivo ainda está na barra."""
        motor = motor_do(self.daemon)
        return frozenset() if motor is None else motor.segurando(CANAL_LUZ)

    @staticmethod
    def _o_hefesto_pode_pintar(controle: Any, jogo: bool) -> bool:
        """A política do tato vivo, perguntada como se houvesse jogo: ``False`` no Nativo ou
        quando o jogo pintou a barra."""
        estado = estado_do_controle(controle, jogo)
        return decidir(CANAL_LUZ, dataclasses.replace(estado, ha_jogo=True))

    def tique_do_laco(self, agora: float) -> int:
        try:
            return self(agora)
        except Exception:
            logger.debug("luz_animada_tique_falhou", exc_info=True)
            return 0


async def luz_animada_loop(daemon: Any, luz: LuzAnimada) -> None:
    passo = Passo(daemon, luz)
    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_DO_LACO_S)
            passo.tique_do_laco(time.monotonic())
    finally:
        try:
            luz.parar_tudo()
        except Exception:
            logger.debug("luz_animada_parar_falhou", exc_info=True)


def start_luz_animada(daemon: Any) -> None:
    """Sobe o laço do efeito. Sem efeito no perfil, ele só relê o arquivo a cada meio segundo."""
    escrever, soltar = escritor_de_producao(daemon)
    luz = LuzAnimada(escrever, soltar)
    daemon._luz_animada = luz
    task = asyncio.create_task(luz_animada_loop(daemon, luz), name="luz_animada_loop")
    daemon._tasks.append(task)
    logger.info("luz_animada_iniciada")


__all__ = [
    "INTERVALO_MINIMO",
    "TETO_DO_PISCAR_HZ",
    "LuzAnimada",
    "Passo",
    "PlanoDoControle",
    "cor_com_o_brilho",
    "cor_no_instante",
    "frequencia_do_piscar_hz",
    "periodo_do_arco_iris_s",
    "periodo_do_respirar_s",
    "plano_do_perfil",
    "start_luz_animada",
]
