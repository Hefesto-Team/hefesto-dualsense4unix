"""A volta dos acessórios no controle: o toque do gesto, as luzinhas medidor e o pulso da barra.

Roda no laço do tato vivo, sem depender da receita nem de haver jogo. Toda escrita passa pelas
guardas de quem escreve: o Modo Nativo cala, o jogo que pinta a barra vence e o toque nunca deixa
os motores presos. O relógio é injetado em cada chamada.
"""

from __future__ import annotations

import asyncio
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
    TETO_POR_CONTROLE,
    TETO_TOTAL,
    Teto,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: A marca do perfil que libera o pulso da barra (``marcas_do_jogo.ADULTO.chave``).
MARCA_DO_PULSO = "adulto"

JANELA_DO_MEDIDOR_S = 2.0
DEGRAU_DO_MEDIDOR = 0  # o brilho forte das luzinhas (0 forte, 2 fraco)
LAMPADAS = 5

PERIODO_MINIMO_S = 1.0  # um ciclo por segundo, no máximo (WCAG 2.3.1)
PERIODO_MAXIMO_S = 4.0
PERIODO_PADRAO_S = 2.0
FUNDO_MAXIMO = 0.5
QUADROS_POR_S = 15
ENTRE_QUADROS_S = 1.0 / QUADROS_POR_S
LUZ_MINIMA_SEM_PISCA = 0.1
SUBIDA_SEM_PISCA_POR_S = 0.5
NIVEL_DO_TETO = 10

#: Os toques como ``(início_ms, fim_ms, esquerdo, direito)``: direito fino, esquerdo grosso.
TOQUE_SOBE = ((0, 40, 0, 200),)
TOQUE_DESCE = ((0, 60, 220, 0),)
TOQUE_PARA = ((0, 160, 255, 255), (260, 420, 255, 255))
TOQUE_NO_TETO = ((0, 40, 0, 200), (100, 140, 0, 200))
_TOQUES = {"sobe": TOQUE_SOBE, "desce": TOQUE_DESCE, "para": TOQUE_PARA}

RGB = tuple[int, int, int]
Passos = tuple[tuple[int, int, int, int], ...]
Luzinhas = tuple[bool, bool, bool, bool, bool]


@dataclass
class Ligacoes:
    """As pontas de fora: o que escreve e o que pergunta. Em produção, o backend e o daemon."""

    #: ``motores(uniq, fraco, forte)``: o motor direito é o fraco, o esquerdo o forte. Em
    #: produção o toque soma ao par que o jogo deixou nos motores, e o zero devolve esse par.
    motores: Callable[[str, int, int], object]
    #: ``(luzinhas, degrau)`` de agora do controle, ou ``None`` se não se sabe lê-las
    ler_luzinhas: Callable[[str], tuple[Luzinhas, int] | None]
    luzinhas: Callable[[str, Luzinhas, int], object]
    barra: Callable[[str, RGB], object]
    soltar_barra: Callable[[str], object]
    pode_falar: Callable[[str], bool]
    o_jogo_pinta: Callable[[str], bool]
    marcas: Callable[[], frozenset[str]]


@dataclass
class _Toque:
    passos: Passos
    inicio: float
    escrito: tuple[int, int] | None = None


@dataclass
class _Medidor:
    ate: float
    luzinhas0: Luzinhas
    degrau0: int
    camada: bool = False
    escrito: tuple[Luzinhas, int] | None = None


@dataclass
class _Pulso:
    cor: RGB
    quente: RGB | None
    fundo: float
    periodo_s: float
    sem_pisca: bool
    ultimo_t: float
    fase: float = 0.0
    brilho: float = 1.0
    escrito: RGB | None = None
    escrito_em: float = float("-inf")


def lampadas_do_nivel(nivel: int) -> int:
    """Quantas lâmpadas o nível acende: ``ceil(nível / 2)``, de 0 a 5."""
    return max(0, min(LAMPADAS, (max(0, nivel) + 1) // 2))


def _luzinhas(acesas: int) -> Luzinhas:
    return (acesas > 0, acesas > 1, acesas > 2, acesas > 3, acesas > 4)


def _cor(valor: Any) -> RGB | None:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        return None
    if any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in valor):
        return None
    r, g, b = (max(0, min(255, round(c))) for c in valor)
    return (r, g, b)


def _misturar(frio: RGB, quente: RGB, t: float) -> RGB:
    r, g, b = (round(a + (c - a) * t) for a, c in zip(frio, quente, strict=True))
    return (r, g, b)


def _escurecer(cor: RGB, fracao: float) -> RGB:
    r, g, b = (max(0, min(255, round(c * fracao))) for c in cor)
    return (r, g, b)


class VoltaDosAcessorios:
    """O que o controle devolve a cada gesto dos acessórios, e o pulso da barra."""

    def __init__(self, ligacoes: Ligacoes, *, teto: Teto | None = None) -> None:
        self._l = ligacoes
        self._teto = teto if teto is not None else Teto(TETO_POR_CONTROLE, TETO_TOTAL)
        self._trava = threading.RLock()
        self._ligado = False
        self._nivel = 0
        self._ajustes: dict[str, Any] = {}
        self._toques: dict[str, _Toque] = {}
        self._medidores: dict[str, _Medidor] = {}
        self._pulsos: dict[str, _Pulso] = {}
        self.escritas = 0

    # -- o que chega do barramento ------------------------------------------------------

    def ao_estado(self, carga: Any, agora: float) -> None:
        """O ``acessorios.estado``: o nível, os ajustes e se a modificação está de pé."""
        if not isinstance(carga, dict):
            return
        with self._trava:
            nivel = carga.get("nivel", 0)
            self._nivel = nivel if isinstance(nivel, int) and not isinstance(nivel, bool) else 0
            ajustes = carga.get("ajustes")
            self._ajustes = dict(ajustes) if isinstance(ajustes, dict) else {}
            self._ligado = carga.get("ligado") is True
            if not self._ligado:
                self.soltar_tudo(agora)

    def ao_gesto(self, carga: Any, agora: float) -> None:
        """O ``acessorios.gesto``: toca, abre o medidor e, na camada, o segura enquanto vale."""
        if not isinstance(carga, dict):
            return
        uniq, gesto = carga.get("uniq"), carga.get("gesto")
        if not isinstance(uniq, str) or not uniq or not isinstance(gesto, str):
            return
        with self._trava:
            antes = self._nivel
            if gesto == "para":
                self._nivel = 0
            if gesto in _TOQUES:
                passos = TOQUE_NO_TETO if gesto == "sobe" and antes >= NIVEL_DO_TETO else None
                self._tocar(uniq, passos or _TOQUES[gesto], agora)
            if gesto in ("sobe", "desce", "para", "nivel_ao_vivo"):
                self._abrir_o_medidor(uniq, agora, camada=False)
            elif gesto == "camada":
                ligou = carga.get("valor") == 1
                self._abrir_o_medidor(uniq, agora, camada=ligou)
                medidor = self._medidores.get(uniq)
                if medidor is not None and not ligou:
                    medidor.camada = False
                    medidor.ate = agora + JANELA_DO_MEDIDOR_S

    def drenar(
        self, gestos: asyncio.Queue[Any], estados: asyncio.Queue[Any], agora: float
    ) -> None:
        """Trata o que as duas filas trazem, os gestos antes do estado que vem depois deles."""
        for fila, tratar in ((gestos, self.ao_gesto), (estados, self.ao_estado)):
            while True:
                try:
                    carga = fila.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    tratar(carga, agora)
                except Exception:
                    logger.debug("volta_dos_acessorios_carga_falhou", exc_info=True)

    # -- o toque ------------------------------------------------------------------------

    def _tocar(self, uniq: str, passos: Passos, agora: float) -> None:
        if self._ajustes.get("toque_de_confirmacao", True) is False:
            return
        if uniq in self._toques or not self._l.pode_falar(uniq):
            return
        if not self._teto.cabe(uniq, agora):
            return
        self._teto.gastar(uniq, agora)
        self._toques[uniq] = _Toque(passos, agora)
        self._andar_o_toque(uniq, agora)

    def _escrever_o_par(self, uniq: str, toque: _Toque, par: tuple[int, int]) -> None:
        toque.escrito = par
        esquerdo, direito = par
        self._l.motores(uniq, direito, esquerdo)
        self.escritas += 1

    def _andar_o_toque(self, uniq: str, agora: float) -> None:
        toque = self._toques.get(uniq)
        if toque is None:
            return
        ms = (agora - toque.inicio) * 1000.0
        par = (0, 0)
        for inicio, fim, esquerdo, direito in toque.passos:
            if inicio <= ms < fim:
                par = (esquerdo, direito)
                break
        if par != toque.escrito:
            self._escrever_o_par(uniq, toque, par)
        if ms >= toque.passos[-1][1]:
            del self._toques[uniq]

    # -- as luzinhas medidor --------------------------------------------------------------

    def _abrir_o_medidor(self, uniq: str, agora: float, *, camada: bool) -> None:
        medidor = self._medidores.get(uniq)
        if medidor is None:
            if not self._l.pode_falar(uniq):
                return
            lido = self._l.ler_luzinhas(uniq)
            if lido is None:
                return
            medidor = _Medidor(agora, lido[0], lido[1])
            self._medidores[uniq] = medidor
        medidor.ate = max(medidor.ate, agora + JANELA_DO_MEDIDOR_S)
        if camada:
            medidor.camada = True
        self._andar_o_medidor(uniq, agora)

    def _andar_o_medidor(self, uniq: str, agora: float) -> None:
        medidor = self._medidores.get(uniq)
        if medidor is None:
            return
        if not self._l.pode_falar(uniq):
            del self._medidores[uniq]  # o Modo Nativo: nada do Hefesto escreve por cima
            return
        if agora >= medidor.ate and not medidor.camada:
            del self._medidores[uniq]
            self._l.luzinhas(uniq, medidor.luzinhas0, medidor.degrau0)
            self.escritas += 1
            return
        alvo = (_luzinhas(lampadas_do_nivel(self._nivel)), DEGRAU_DO_MEDIDOR)
        if medidor.escrito != alvo:
            medidor.escrito = alvo
            self._l.luzinhas(uniq, *alvo)
            self.escritas += 1

    # -- o pulso da barra -----------------------------------------------------------------

    def _recusa_do_pulso(self, uniq: str) -> str | None:
        if not self._l.pode_falar(uniq):
            return "modo_nativo"
        if self._l.o_jogo_pinta(uniq):
            return "o_jogo_pinta_a_barra"
        if MARCA_DO_PULSO not in self._l.marcas():
            return "sem_a_marca_adulto"
        if self._ajustes.get("pulso_da_barra") is not True:
            return "pulso_desligado"
        return None

    def pulsar(self, uniq: str, pedido: dict[str, Any], agora: float) -> dict[str, Any]:
        """O ``luz.pulso`` da porta: começa, retoca ou solta o pulso da barra deste controle."""
        with self._trava:
            if pedido.get("parar") is True:
                tinha = uniq in self._pulsos
                self._soltar_o_pulso(uniq)
                return {"aplicado": tinha, "motivo": "solto" if tinha else "nada_a_soltar"}
            recusa = self._recusa_do_pulso(uniq)
            if recusa is not None:
                self._soltar_o_pulso(uniq)
                return {"aplicado": False, "motivo": recusa}
            cor = _cor(pedido.get("cor"))
            if cor is None:
                return {"aplicado": False, "motivo": "cor_ilegivel"}
            periodo = pedido.get("periodo_s", PERIODO_PADRAO_S)
            periodo = float(periodo) if isinstance(periodo, (int, float)) else PERIODO_PADRAO_S
            periodo = max(PERIODO_MINIMO_S, min(PERIODO_MAXIMO_S, periodo))
            fundo = pedido.get("fundo", 0.0)
            fundo = float(fundo) if isinstance(fundo, (int, float)) else 0.0
            antigo = self._pulsos.get(uniq)
            pulso = _Pulso(
                cor=cor,
                quente=_cor(pedido.get("cor_quente")),
                fundo=max(0.0, min(FUNDO_MAXIMO, fundo)),
                periodo_s=periodo,
                sem_pisca=self._ajustes.get("sem_pisca") is True,
                ultimo_t=agora,
                fase=0.0 if antigo is None else antigo.fase,
                brilho=self._brilho_sem_pisca(),
            )
            if antigo is not None:
                pulso.escrito, pulso.escrito_em = antigo.escrito, antigo.escrito_em
                pulso.brilho = antigo.brilho if pulso.sem_pisca else pulso.brilho
            self._pulsos[uniq] = pulso
            self._andar_o_pulso(uniq, agora)
            return {"aplicado": True, "motivo": "pulsando", "periodo_s": periodo}

    def _brilho_sem_pisca(self) -> float:
        return LUZ_MINIMA_SEM_PISCA + (1.0 - LUZ_MINIMA_SEM_PISCA) * self._calor()

    def _calor(self) -> float:
        """Onde o nível está entre o 1 e o 10, de 0 a 1."""
        return (max(self._nivel, 1) - 1) / (NIVEL_DO_TETO - 1)

    def _soltar_o_pulso(self, uniq: str) -> None:
        if self._pulsos.pop(uniq, None) is not None:
            self._l.soltar_barra(uniq)

    def _andar_o_pulso(self, uniq: str, agora: float) -> None:
        pulso = self._pulsos.get(uniq)
        if pulso is None:
            return
        if self._recusa_do_pulso(uniq) is not None:
            self._soltar_o_pulso(uniq)
            return
        passou = max(0.0, agora - pulso.ultimo_t)
        pulso.ultimo_t = agora
        calor = self._calor()
        cor = pulso.cor if pulso.quente is None else _misturar(pulso.cor, pulso.quente, calor)
        if pulso.sem_pisca:
            passo = SUBIDA_SEM_PISCA_POR_S * passou
            pulso.brilho += max(-passo, min(passo, self._brilho_sem_pisca() - pulso.brilho))
            fracao = pulso.brilho
        else:
            pulso.fase = (pulso.fase + passou / pulso.periodo_s) % 1.0
            onda = 0.5 - 0.5 * math.cos(2.0 * math.pi * pulso.fase)
            fracao = pulso.fundo + (1.0 - pulso.fundo) * onda
        quadro = _escurecer(cor, fracao)
        if quadro == pulso.escrito or agora - pulso.escrito_em < ENTRE_QUADROS_S:
            return
        pulso.escrito, pulso.escrito_em = quadro, agora
        self._l.barra(uniq, quadro)
        self.escritas += 1

    # -- o tique e o fim --------------------------------------------------------------------

    def tique(self, agora: float) -> int:
        """Anda o toque, o medidor e o pulso de cada controle; devolve quantas escritas saíram."""
        antes = self.escritas
        with self._trava:
            for andar, em_curso in (
                (self._andar_o_toque, self._toques),
                (self._andar_o_medidor, self._medidores),
                (self._andar_o_pulso, self._pulsos),
            ):
                for uniq in list(em_curso):
                    try:
                        andar(uniq, agora)
                    except Exception:
                        logger.debug("volta_dos_acessorios_tique_falhou", exc_info=True)
        return self.escritas - antes

    def segurando_a_barra(self) -> frozenset[str]:
        """Os controles cuja barra o pulso segura: o efeito do perfil espera por eles."""
        with self._trava:
            return frozenset(self._pulsos)

    def soltar_tudo(self, agora: float) -> None:
        """A modificação parou ou a conexão caiu: o pulso solta, o medidor volta, o toque zera."""
        with self._trava:
            for uniq in list(self._pulsos):
                self._soltar_o_pulso(uniq)
            for uniq, medidor in list(self._medidores.items()):
                del self._medidores[uniq]
                if self._l.pode_falar(uniq):
                    self._l.luzinhas(uniq, medidor.luzinhas0, medidor.degrau0)
                    self.escritas += 1
            for uniq, toque in list(self._toques.items()):
                del self._toques[uniq]
                if toque.escrito not in (None, (0, 0)):
                    self._escrever_o_par(uniq, toque, (0, 0))


def somar_ao_par_do_jogo(toque: tuple[int, int], jogo: tuple[int, int]) -> tuple[int, int]:
    """O ``(fraco, forte)`` do toque somado ao do jogo, com teto 255: o toque nunca cala o jogo."""
    return (min(255, toque[0] + jogo[0]), min(255, toque[1] + jogo[1]))


def volta_de_producao(daemon: Any) -> VoltaDosAcessorios:
    """A volta ligada ao serviço vivo: o backend escreve, o daemon responde às guardas."""
    from hefesto_dualsense4unix.core.controller import OutputSpec
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.lifecycle import o_hefesto_fala_no_modo
    from hefesto_dualsense4unix.daemon.subsystems.luz_animada import escritor_de_producao
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
        _barras_dos_motores,
        _na_barra,
        controles_do_daemon,
        estado_do_controle,
    )
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import par_nos_motores
    from hefesto_dualsense4unix.mods.porta import o_jogo_escreve_no_servico

    controller = getattr(daemon, "controller", None)
    o_jogo_escreve = o_jogo_escreve_no_servico(daemon)
    barra, soltar = escritor_de_producao(daemon)

    def motores(uniq: str, fraco: int, forte: int) -> object:
        escrever = getattr(controller, "set_rumble_for", None)
        if not callable(escrever):
            return False
        forte_pct, fraco_pct = _barras_dos_motores(daemon, uniq)
        do_jogo = par_nos_motores(daemon, uniq)
        return escrever(uniq, *somar_ao_par_do_jogo(
            (_na_barra(fraco, fraco_pct), _na_barra(forte, forte_pct)), do_jogo,
        ))

    def ler_luzinhas(uniq: str) -> tuple[Luzinhas, int] | None:
        ler = getattr(controller, "resolved_player_leds_for", None)
        luzes = ler(uniq) if callable(ler) else None
        if not isinstance(luzes, tuple) or len(luzes) != LAMPADAS:
            return None
        brilho = getattr(controller, "brilho_das_luzes_para", None)
        degrau = brilho(uniq) if callable(brilho) else None
        return (luzes, degrau if isinstance(degrau, int) else DEGRAU_DO_MEDIDOR)

    def luzinhas(uniq: str, acesas: Luzinhas, degrau: int) -> object:
        escrever = getattr(controller, "apply_output_for", None)
        if not callable(escrever):
            return False
        return escrever(uniq, OutputSpec(player_leds=acesas, player_led_brightness=degrau))

    def pode_falar(uniq: str) -> bool:
        for controle in controles_do_daemon(daemon):
            if controle.uniq == uniq:
                return o_hefesto_fala_no_modo(estado_do_controle(controle, True).modo)
        return False

    def marcas() -> frozenset[str]:
        bus = getattr(daemon, "bus", None)
        ultimo = getattr(bus, "ultimo", None)  # (noqa-acento): o nome do método do barramento
        carga = ultimo(EventTopic.PERFIL_TROCOU) if callable(ultimo) else None
        lista = carga.get("marcas") if isinstance(carga, dict) else None
        return frozenset(str(m) for m in lista) if isinstance(lista, (list, tuple)) else frozenset()

    return VoltaDosAcessorios(Ligacoes(
        motores=motores,
        ler_luzinhas=ler_luzinhas,
        luzinhas=luzinhas,
        barra=barra,
        soltar_barra=soltar,
        pode_falar=pode_falar,
        o_jogo_pinta=lambda uniq: o_jogo_escreve(uniq, "luz"),
        marcas=marcas,
    ))


__all__ = [
    "DEGRAU_DO_MEDIDOR",
    "JANELA_DO_MEDIDOR_S",
    "MARCA_DO_PULSO",
    "PERIODO_MAXIMO_S",
    "PERIODO_MINIMO_S",
    "TOQUE_DESCE",
    "TOQUE_NO_TETO",
    "TOQUE_PARA",
    "TOQUE_SOBE",
    "Ligacoes",
    "VoltaDosAcessorios",
    "lampadas_do_nivel",
    "somar_ao_par_do_jogo",
    "volta_de_producao",
]
