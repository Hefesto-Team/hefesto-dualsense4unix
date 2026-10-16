"""Os gestos do botão PS que comandam os acessórios (OS-GESTOS-DO-PS-COMANDAM-OS-ACESSORIOS-01).

Uma máquina por controle (``de=<MAC>``), chamada pelo ``HotkeyManager``. Fora do laço dos combos
genéricos, que espera 150 ms e dispara uma vez: aqui o gesto sai na BORDA do gatilho. Emite
``sobe``, ``desce``, ``para``, ``perfil_seguinte``, ``perfil_anterior``, ``surto``,
``nivel_ao_vivo`` e ``camada`` por ``emitir(de, gesto, valor)``, nunca um botão cru. Enquanto o
gesto de um membro vale, o botão dele e o EIXO do gatilho ficam calados ao jogo, por controle.
Só vale com uma modificação de acessórios que devolveu o estado com algum aparelho (``valem``);
sem ela, PS + R2 é o que sempre foi. O contrato: docs/protocol/porta-das-modificacoes.md.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

PS_BUTTON = "ps"

#: Gatilho analógico (0 a 255): aperta aos 20 % e só solta abaixo de 10 %, para o ruído do curso
#: não picotar o gesto.
GATILHO_APERTA = 51
GATILHO_SOLTA = 26

LIMIAR_DO_FUNDO_PADRAO = 0.90
REPETE_DEPOIS_DE_S = 0.5
REPETE_A_CADA_S = 0.3
SURTO_EM_S = 0.35
PS_DUPLO_S = 0.4
CAMADA_PADRAO_S = 6.0
PARAR_SEGURANDO_S = 0.6
NIVEL_AO_VIVO_INTERVALO_S = 1 / 20
#: O membro que já estava apertado até este tempo antes do PS entra no gesto: ninguém aperta
#: os dois no mesmo milissegundo.
GRACA_DO_PS_S = 0.1

#: O membro do gesto → o nome do botão que o jogo deixa de receber.
BOTAO_DO_MEMBRO: dict[str, str] = {
    "r2": "r2_btn",
    "l2": "l2_btn",
    "r1": "r1",
    "l1": "l1",
    "dpad_left": "dpad_left",
    "dpad_right": "dpad_right",
}
_MEMBROS_NORMAIS = ("r2", "l2", "r1", "l1")
_MEMBROS_DO_LADO_UNICO = (*_MEMBROS_NORMAIS, "dpad_left", "dpad_right")

#: Os gestos que a modificação recebe (o vocabulário público).
GESTOS = (
    "sobe", "desce", "para", "perfil_seguinte", "perfil_anterior", "nivel_ao_vivo", "surto",
    "camada",
)


@dataclass(frozen=True)
class Opcoes:
    """As opções da modificação que mexem nos gestos (todas nascem desligadas, menos o limiar)."""

    limiar_fundo: float = LIMIAR_DO_FUNDO_PADRAO
    acelerador: bool = False
    camada: bool = False
    #: Segundos sem gesto até a camada desligar sozinha; 0 = «até eu desligar».
    camada_s: float = CAMADA_PADRAO_S
    lado_unico: bool = False
    gestos_no_nativo: bool = False

    @classmethod
    def de(cls, bruto: Mapping[str, Any] | None) -> Opcoes:
        """Lê as opções do estado da modificação; valor ilegível volta ao padrão. Nunca levanta."""
        if not isinstance(bruto, Mapping):
            return cls()
        return cls(
            limiar_fundo=_limiar(bruto.get("limiar_fundo")),
            acelerador=bruto.get("acelerador") is True,
            camada=bruto.get("camada") is True,
            camada_s=_segundos(bruto.get("camada_s"), CAMADA_PADRAO_S),
            lado_unico=bruto.get("lado_unico") is True,
            gestos_no_nativo=bruto.get("gestos_no_nativo") is True,
        )

    def membros(self) -> tuple[str, ...]:
        return _MEMBROS_DO_LADO_UNICO if self.lado_unico else _MEMBROS_NORMAIS


def _limiar(valor: Any) -> float:
    """50 a 100 %: aceita 0,5 a 1 ou 50 a 100."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return LIMIAR_DO_FUNDO_PADRAO
    fracao = valor / 100 if valor > 1 else float(valor)
    return min(1.0, max(0.5, fracao))


def _segundos(valor: Any, padrao: float) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return padrao
    return max(0.0, float(valor))


@dataclass
class _Mao:
    """O que a máquina guarda de UM controle."""

    t: float = 0.0
    #: Os membros que o gesto cala ao jogo: entram na borda e saem quando o próprio membro solta.
    calados: set[str] = field(default_factory=set)
    #: Quando cada membro foi visto apertado pela primeira vez (ausente = solto).
    vistos: dict[str, float] = field(default_factory=dict)
    ps_apertado: bool = False
    ps_toques: list[float] = field(default_factory=list)
    camada: bool = False
    camada_ate: float | None = None
    #: O PS desta mão fez gesto (ou virou a camada): o toque dele não abre a Steam.
    usou_o_ps: bool = False
    #: A camada virou neste PS: o toque pendente que espera o duplo é cancelado.
    camada_virou: bool = False
    repete_ate: float = 0.0
    r2_valor: float | None = None
    r2_nivel_em: float = -1.0
    ultimo_sobe_em: float | None = None
    ultimo_foi_sobe: bool = False
    l2_cruzou: bool = False
    segurou: dict[str, float] = field(default_factory=dict)
    parou_segurando: set[str] = field(default_factory=set)


class GestosDosAcessorios:
    """A máquina dos gestos, por controle. Sem relógio próprio: o instante vem de quem chama."""

    def __init__(
        self,
        *,
        valem: Callable[[str | None], Opcoes | None],
        emitir: Callable[[str | None, str, float], None],
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._valem = valem
        self._emitir = emitir
        self._relogio = relogio
        self._maos: dict[str | None, _Mao] = {}

    # -- perguntas baratas ---------------------------------------------------

    def opcoes_de(self, de: str | None) -> Opcoes | None:
        """As opções que valem para o controle ``de``, ou None (os gestos não valem)."""
        try:
            return self._valem(de)
        except Exception as exc:
            logger.debug("gestos_dos_acessorios_sem_estado", err=str(exc))
            return None

    def valem(self, de: str | None = None) -> bool:
        return self.opcoes_de(de) is not None

    def ps_espera_s(self, de: str | None) -> float:
        """Quanto o PS sozinho espera antes de abrir a Steam: 0,4 s só com a camada ligada."""
        opcoes = self.opcoes_de(de)
        return PS_DUPLO_S if opcoes is not None and opcoes.camada else 0.0

    def camada_ligada(self, de: str | None) -> bool:
        mao = self._maos.get(de)
        return bool(mao and mao.camada)

    def parceiros(self, de: str | None) -> frozenset[str]:
        """Os botões que fazem gesto com o PS neste controle (vazio sem gestos)."""
        opcoes = self.opcoes_de(de)
        if opcoes is None:
            return frozenset()
        return frozenset(BOTAO_DO_MEMBRO[m] for m in opcoes.membros())

    def consumir(self, de: str | None) -> tuple[bool, bool]:
        """``(o PS fez gesto, a camada virou)`` desde a última pergunta; zera os dois."""
        mao = self._maos.get(de)
        if mao is None:
            return False, False
        usou, virou = mao.usou_o_ps, mao.camada_virou
        mao.usou_o_ps = mao.camada_virou = False
        return usou, virou

    def soltar_quem_saiu(self, ficam: Iterable[str | None]) -> None:
        manter = set(ficam)
        for chave in [c for c in self._maos if c not in manter]:
            del self._maos[chave]

    # -- o que o jogo não vê ---------------------------------------------------

    def botoes_calados(self, de: str | None) -> frozenset[str]:
        mao = self._maos.get(de)
        if mao is None:
            return frozenset()
        return frozenset(BOTAO_DO_MEMBRO[m] for m in mao.calados)

    def eixos_calados(self, de: str | None) -> frozenset[str]:
        """Os eixos de gatilho (``l2``, ``r2``) que o gesto de ``de`` cala ao jogo."""
        mao = self._maos.get(de)
        if mao is None:
            return frozenset()
        return frozenset(m for m in mao.calados if m in ("l2", "r2"))

    # -- o tique -----------------------------------------------------------------

    def avaliar(
        self,
        pressed: Iterable[str],
        gatilhos: tuple[int, int] | None,
        *,
        now: float | None,
        de: str | None,
        ps_virtual: bool = False,
    ) -> Opcoes | None:
        """Lê um instante do controle ``de``: emite o que o instante dispara e atualiza o latch.

        Idempotente: o mesmo instante lido duas vezes (o laço do pad e o dos atalhos leem o mesmo
        tique) não emite duas vezes: o gesto nasce da MUDANÇA do membro. Devolve as opções que
        valem, ou None quando os gestos não valem (e então não há latch nenhum).
        """
        opcoes = self.opcoes_de(de)
        if opcoes is None:
            self._maos.pop(de, None)
            return None
        mao = self._maos.get(de)
        if mao is None:
            mao = self._maos[de] = _Mao()
        t = now if now is not None else self._relogio()
        t = max(t, mao.t)
        mao.t = t
        botoes = frozenset(str(b).lower() for b in pressed)
        ps = PS_BUTTON in botoes or ps_virtual

        if mao.camada and mao.camada_ate is not None and t >= mao.camada_ate:
            mao.camada = False
            mao.camada_ate = None
        if not opcoes.camada and mao.camada:
            mao.camada = False
            mao.camada_ate = None

        borda_do_ps = ps and not mao.ps_apertado
        mao.ps_apertado = ps
        if borda_do_ps and PS_BUTTON in botoes:
            self._toque_do_ps(mao, opcoes, t, de)
        ativo = ps or mao.camada

        membros = opcoes.membros()
        for membro in list(mao.calados):
            if membro not in membros:  # o «Lado único» foi desligado no meio do aperto
                mao.calados.discard(membro)
        for membro in membros:
            apertado = self._apertado(membro, botoes, gatilhos, segurando=membro in mao.vistos)
            if not apertado:
                mao.vistos.pop(membro, None)
                if membro in mao.calados:
                    mao.calados.discard(membro)
                    self._soltou(mao, opcoes, membro, t, de)
                continue
            antes = mao.vistos.get(membro)
            if antes is None:
                mao.vistos[membro] = antes = t
                borda = True
            else:
                borda = borda_do_ps and t - antes <= GRACA_DO_PS_S
            if membro in mao.calados:
                self._segurando(mao, opcoes, membro, gatilhos, t, de)
            elif ativo and borda:
                mao.calados.add(membro)
                self._comecou(mao, opcoes, membro, gatilhos, t, de, com_o_ps=ps)
        return opcoes

    @staticmethod
    def _apertado(
        membro: str, botoes: frozenset[str], gatilhos: tuple[int, int] | None, *, segurando: bool
    ) -> bool:
        if membro in ("l2", "r2"):
            if BOTAO_DO_MEMBRO[membro] in botoes:
                return True
            if gatilhos is None:
                return False
            cru = gatilhos[0] if membro == "l2" else gatilhos[1]
            return cru >= (GATILHO_SOLTA if segurando else GATILHO_APERTA)
        return BOTAO_DO_MEMBRO[membro] in botoes

    # -- o PS e a camada -----------------------------------------------------------

    def _toque_do_ps(self, mao: _Mao, opcoes: Opcoes, t: float, de: str | None) -> None:
        """A borda do PS: o segundo toque em 0,4 s liga ou desliga a camada (se a opção vale)."""
        recentes = [x for x in mao.ps_toques if t - x <= PS_DUPLO_S]
        if opcoes.camada and recentes:
            mao.ps_toques = []
            mao.camada = not mao.camada
            mao.camada_ate = t + opcoes.camada_s if mao.camada and opcoes.camada_s > 0 else None
            mao.camada_virou = True
            mao.usou_o_ps = True
            self._dizer(de, "camada", 1 if mao.camada else 0)
            return
        recentes.append(t)
        mao.ps_toques = recentes

    # -- cada membro -----------------------------------------------------------------

    def _dizer(self, de: str | None, gesto: str, valor: float) -> None:
        mao = self._maos.get(de)
        if mao is not None and gesto != "camada" and mao.camada and mao.camada_ate is not None:
            opcoes = self.opcoes_de(de)
            if opcoes is not None and opcoes.camada_s > 0:
                mao.camada_ate = mao.t + opcoes.camada_s
        try:
            self._emitir(de, gesto, valor)
        except Exception as exc:  # quem escuta nunca derruba o tique
            logger.warning("gesto_dos_acessorios_nao_saiu", gesto=gesto, err=str(exc))

    def _sobe(self, mao: _Mao, t: float, de: str | None) -> None:
        recente = mao.ultimo_sobe_em is not None and t - mao.ultimo_sobe_em <= SURTO_EM_S
        if recente and mao.ultimo_foi_sobe:
            mao.ultimo_foi_sobe = False
            mao.ultimo_sobe_em = t
            self._dizer(de, "surto", 1)
            return
        mao.ultimo_sobe_em = t
        mao.ultimo_foi_sobe = True
        self._dizer(de, "sobe", 1)

    def _comecou(
        self,
        mao: _Mao,
        opcoes: Opcoes,
        membro: str,
        gatilhos: tuple[int, int] | None,
        t: float,
        de: str | None,
        *,
        com_o_ps: bool,
    ) -> None:
        if com_o_ps:
            mao.usou_o_ps = True
        if opcoes.lado_unico:
            self._comecou_lado_unico(mao, membro, t, de)
            return
        if membro == "r2":
            if opcoes.acelerador:
                mao.r2_valor = None
                mao.r2_nivel_em = -1.0
                self._nivel_ao_vivo(mao, gatilhos, t, de)
            else:
                mao.repete_ate = t + REPETE_DEPOIS_DE_S
                self._sobe(mao, t, de)
        elif membro == "l2":
            mao.l2_cruzou = False
        elif membro == "r1":
            self._dizer(de, "perfil_seguinte", 1)
        elif membro == "l1":
            self._dizer(de, "perfil_anterior", 1)

    def _comecou_lado_unico(self, mao: _Mao, membro: str, t: float, de: str | None) -> None:
        """«Lado único»: R2/L2 sobe, R1/L1 desce e, segurado, para; o direcional troca o perfil."""
        if membro in ("r2", "l2"):
            mao.repete_ate = t + REPETE_DEPOIS_DE_S
            self._sobe(mao, t, de)
        elif membro in ("r1", "l1"):
            mao.segurou[membro] = t
            mao.parou_segurando.discard(membro)
        elif membro == "dpad_right":
            self._dizer(de, "perfil_seguinte", 1)
        elif membro == "dpad_left":
            self._dizer(de, "perfil_anterior", 1)

    def _segurando(
        self,
        mao: _Mao,
        opcoes: Opcoes,
        membro: str,
        gatilhos: tuple[int, int] | None,
        t: float,
        de: str | None,
    ) -> None:
        if opcoes.lado_unico:
            if membro in ("r2", "l2") and t >= mao.repete_ate:
                mao.repete_ate = max(mao.repete_ate + REPETE_A_CADA_S, t)
                self._dizer(de, "sobe", 1)
            elif (
                membro in ("r1", "l1")
                and membro not in mao.parou_segurando
                and t - mao.segurou.get(membro, t) >= PARAR_SEGURANDO_S
            ):
                mao.parou_segurando.add(membro)
                self._dizer(de, "para", 1)
            return
        if membro == "r2":
            if opcoes.acelerador:
                self._nivel_ao_vivo(mao, gatilhos, t, de)
            elif t >= mao.repete_ate:
                mao.repete_ate = max(mao.repete_ate + REPETE_A_CADA_S, t)
                self._dizer(de, "sobe", 1)
        elif (
            membro == "l2"
            and not mao.l2_cruzou
            and gatilhos is not None
            and gatilhos[0] >= round(opcoes.limiar_fundo * 255)
        ):
            mao.l2_cruzou = True
            self._dizer(de, "para", 1)

    def _soltou(self, mao: _Mao, opcoes: Opcoes, membro: str, t: float, de: str | None) -> None:
        if opcoes.lado_unico:
            if membro in ("r1", "l1"):
                parou = membro in mao.parou_segurando
                mao.parou_segurando.discard(membro)
                mao.segurou.pop(membro, None)
                if not parou:
                    self._dizer(de, "desce", 1)
            return
        if membro == "l2":
            cruzou, mao.l2_cruzou = mao.l2_cruzou, False
            if not cruzou:
                self._dizer(de, "desce", 1)
        elif membro == "r2" and opcoes.acelerador:
            mao.r2_valor = None
            self._dizer(de, "nivel_ao_vivo", 0.0)

    def _nivel_ao_vivo(
        self, mao: _Mao, gatilhos: tuple[int, int] | None, t: float, de: str | None
    ) -> None:
        """«Acelerador»: a pressão do R2, de 0 a 1, no máximo 20 por segundo e só quando muda."""
        if t - mao.r2_nivel_em < NIVEL_AO_VIVO_INTERVALO_S:
            return
        valor = 1.0 if gatilhos is None else round(min(255, max(0, gatilhos[1])) / 255, 3)
        if valor == mao.r2_valor:
            return
        mao.r2_valor = valor
        mao.r2_nivel_em = t
        self._dizer(de, "nivel_ao_vivo", valor)


__all__ = [
    "BOTAO_DO_MEMBRO",
    "GATILHO_APERTA",
    "GATILHO_SOLTA",
    "GESTOS",
    "GestosDosAcessorios",
    "Opcoes",  # (noqa-acento): nome da classe
]
