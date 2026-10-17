"""O tremor e o aperto junto não decidem o botão: repique, aperto mínimo e botão que trava.

Dono único e puro: quem chama passa o tempo do laço. Entra ANTES do remapeamento, nos dois
caminhos do pad virtual (o do primeiro controle e o dos outros jogadores) e na tabela de
teclas, para que o resto do produto já receba o botão limpo. O estado é por controle.
Repique: o aperto que volta antes de N ms depois do anterior soltar é ignorado (o resto do
aperto também). Aperto mínimo: só conta o aperto que dura N ms. Botão que trava: fica preso
até o próximo aperto de outro botão, e os dois saem e soltam juntos. O PS travado (o gesto
do PS sem apertar dois juntos) mora no ``HotkeyManager``; aqui só mora o número.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from hefesto_dualsense4unix.core.ativacao_de_botao import (
    CAMPOS_DO_FILTRO,
    LIMIAR_DO_GATILHO,
    PARADA_S,
    campos_juntos,
    chave,
)
from hefesto_dualsense4unix.core.remapeamento_de_botao import (
    FORCA_CHEIA,
    GATILHOS,
    REMAPEAVEIS,
)

#: Os botões que o filtro alcança: os mesmos que a troca de botões alcança.
FILTRAVEIS: Final[tuple[str, ...]] = REMAPEAVEIS

#: O que a tela propõe ao ligar (a validar pelo usuário); desligado, o número é zero.
REPIQUE_DE_FABRICA_MS: Final = 120
APERTO_MINIMO_DE_FABRICA_MS: Final = 50
PS_TRAVADO_DE_FABRICA_MS: Final = 600

#: As faixas que a tela oferece e o motor aplica; zero desliga.
FAIXA_DO_REPIQUE_MS: Final = (20, 1000)
FAIXA_DO_APERTO_MINIMO_MS: Final = (10, 500)
FAIXA_DO_PS_TRAVADO_MS: Final = (100, 3000)

CAMPOS: Final[tuple[str, ...]] = CAMPOS_DO_FILTRO

_ATRIBUTO_DA_MESA: Final = "_filtro_de_botao_da_mesa"
_ATRIBUTO_POR_PECA: Final = "_filtro_de_botao_por_peca"
_ATRIBUTO_DOS_ESTADOS: Final = "_filtro_de_botao_estados"


@dataclass(frozen=True)
class Filtro:
    """O que a pessoa escolheu para o tremor e o aperto junto, já em segundos."""

    repique_s: float = 0.0
    aperto_minimo_s: float = 0.0
    travar: frozenset[str] = frozenset()
    ps_travado_s: float = 0.0

    @property
    def liga(self) -> bool:
        """Algo a fazer no caminho do pad virtual (o PS travado mora no gesto, não aqui)."""
        return self.repique_s > 0 or self.aperto_minimo_s > 0 or bool(self.travar)

    @property
    def algum(self) -> bool:
        return self.liga or self.ps_travado_s > 0


def montar(secao: object, secao_da_peca: object = None) -> Filtro | None:
    """O filtro do perfil, com a seção da peça por cima campo a campo. ``None`` = sem filtro."""
    campos = campos_juntos(secao, secao_da_peca)
    travar = [n for n in (campos.get("travar") or ()) if n in set(FILTRAVEIS)]
    filtro = Filtro(
        repique_s=_ms(campos.get("repique_ms"), FAIXA_DO_REPIQUE_MS),
        aperto_minimo_s=_ms(campos.get("aperto_minimo_ms"), FAIXA_DO_APERTO_MINIMO_MS),
        travar=frozenset(travar),
        ps_travado_s=_ms(campos.get("ps_travado_ms"), FAIXA_DO_PS_TRAVADO_MS),
    )
    return filtro if filtro.algum else None


def _ms(valor: object, faixa: tuple[int, int]) -> float:
    """Zero (ou o que não é número) desliga; o resto fica na faixa."""
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor <= 0:
        return 0.0
    return min(max(int(valor), faixa[0]), faixa[1]) / 1000.0


@dataclass
class _Fio:
    """Um botão: o que a mão faz e o que o filtro deixa passar."""

    mao: bool = False
    desde: float = 0.0
    soltou_em: float | None = None
    ignorado: bool = False
    passa: bool = False


@dataclass
class FiltroDoControle:
    """O estado de UM controle. Mora no dono (o store do daemon), pela identidade dele."""

    fios: dict[str, _Fio] = field(default_factory=dict)
    travados: set[str] = field(default_factory=set)
    parceiros: set[str] = field(default_factory=set)
    anterior: float | None = None

    def vazio(self) -> bool:
        """Nada preso: nem botão travado, nem aperto esperando o mínimo."""
        return not self.travados and not any(f.mao or f.passa for f in self.fios.values())

    def passo(
        self,
        filtro: Filtro,
        botoes: frozenset[str],
        l2: int,
        r2: int,
        agora: float,
        soltos: frozenset[str] = frozenset(),
    ) -> tuple[frozenset[str], int, int, frozenset[str]]:
        """Um tique: o que a mão apertou → o que o resto do produto vai ver.

        Devolve ``(botões, l2, r2, soltos)``; ``soltos`` são os apertos que subiram e
        desceram entre dois tiques (contam como um toque).
        """
        intervalo = 0.0
        if self.anterior is not None:
            if agora - self.anterior > PARADA_S:
                self.fios.clear()
                self.travados.clear()
                self.parceiros.clear()
            else:
                intervalo = agora - self.anterior
        self.anterior = agora
        forca = {"l2": l2, "r2": r2}
        passam: dict[str, bool] = {}
        maos: set[str] = set()
        subiram: list[str] = []
        toques: set[str] = set()
        for nome in FILTRAVEIS:
            btn = GATILHOS.get(nome, nome)
            mao = btn in botoes or nome in botoes or (
                nome in forca and forca[nome] >= LIMIAR_DO_GATILHO)
            toque = (btn in soltos or nome in soltos) and not mao
            fio = self.fios.setdefault(nome, _Fio())
            antes = fio.passa
            passam[nome] = self._um(filtro, fio, mao, toque, agora, intervalo)
            if mao:
                maos.add(nome)
            if toque and passam[nome]:
                toques.add(nome)
            elif passam[nome] and not antes:
                subiram.append(nome)
        sai = self._travar(filtro, passam, subiram, toques)
        return self._saida(botoes, l2, r2, soltos, sai, passam, maos, toques)

    @staticmethod
    def _um(
        filtro: Filtro, fio: _Fio, mao: bool, toque: bool, agora: float, intervalo: float
    ) -> bool:
        """O botão passa neste tique? Atualiza o repique e o mínimo."""
        if toque:
            # Subiu e desceu entre dois tiques: durou menos que o intervalo.
            ruim = (
                filtro.aperto_minimo_s > 0 and intervalo < filtro.aperto_minimo_s) or (
                filtro.repique_s > 0 and fio.soltou_em is not None
                and agora - fio.soltou_em < filtro.repique_s)
            fio.soltou_em = agora
            return not ruim
        if mao and not fio.mao:
            fio.desde = agora
            fio.ignorado = (
                filtro.repique_s > 0 and fio.soltou_em is not None
                and agora - fio.soltou_em < filtro.repique_s)
        elif not mao and fio.mao:
            fio.soltou_em = agora
        fio.mao = mao
        fio.passa = mao and not fio.ignorado and agora - fio.desde >= filtro.aperto_minimo_s
        return fio.passa

    def _travar(
        self, filtro: Filtro, passam: dict[str, bool], subiram: list[str], toques: set[str]
    ) -> set[str]:
        """Os botões que ficam apertados pela trava neste tique (além dos que a mão passa)."""
        if not filtro.travar and not self.travados:
            return set()
        # Primeiro as travas, depois os parceiros: L1 e Cruz juntos são um par, não um acaso.
        for nome in [*subiram, *sorted(toques)]:
            if nome in filtro.travar:
                self.travados.symmetric_difference_update({nome})
        for nome in [*subiram, *sorted(toques)]:
            if nome not in filtro.travar and self.travados:
                self.parceiros.add(nome)
        sai = set(self.travados)
        # O parceiro soltou: a trava solta com ele, no mesmo tique. Um parceiro que foi só um
        # toque ainda entrega ao jogo os dois juntos NESTE tique, e solta no seguinte.
        segurados = {p for p in self.parceiros if passam.get(p) and p not in toques}
        if self.parceiros and not segurados:
            self.travados.clear()
            self.parceiros.clear()
            return sai if toques else set()
        return sai

    @staticmethod
    def _saida(
        botoes: frozenset[str],
        l2: int,
        r2: int,
        soltos: frozenset[str],
        travados: set[str],
        passam: dict[str, bool],
        maos: set[str],
        toques: set[str],
    ) -> tuple[frozenset[str], int, int, frozenset[str]]:
        forca = {"l2": l2, "r2": r2}
        nossos = {*FILTRAVEIS, *GATILHOS.values()}
        saida = {b for b in botoes if b not in nossos}
        resto = {b for b in soltos if b not in nossos}
        for nome in FILTRAVEIS:
            btn = GATILHOS.get(nome, nome)
            if nome in toques:
                resto.add(btn)
            if nome in travados or (passam[nome] and nome not in toques):
                saida.add(btn)
            if nome in forca:
                if nome in maos and not passam[nome]:
                    forca[nome] = 0
                elif nome in travados and forca[nome] < LIMIAR_DO_GATILHO:
                    forca[nome] = FORCA_CHEIA
        return frozenset(saida), forca["l2"], forca["r2"], frozenset(resto)


def definir_ativo(
    dono: object,
    mesa: Filtro | None,
    por_peca: Mapping[str, Filtro | None] | None = None,
) -> None:
    """Guarda o filtro ATIVO no dono (o ``StateStore``), e solta tudo o que estava preso."""
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DA_MESA, mesa)
    limpo = {chave(k): v for k, v in (por_peca or {}).items() if chave(k)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))
    esquecer(dono)


def da_peca(dono: object, uniq: object) -> Filtro | None:
    """O filtro que vale para o controle ``uniq`` AGORA, ou ``None``."""
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    if isinstance(mapa, Mapping) and uniq:
        k = chave(uniq)
        if k in mapa:
            valor = mapa[k]
            return valor if isinstance(valor, Filtro) and valor.algum else None
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    return mesa if isinstance(mesa, Filtro) and mesa.algum else None


def alguma(dono: object) -> bool:
    """Algum controle tem filtro de botão neste perfil? Custo de dois ``getattr`` no tique."""
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    if isinstance(mesa, Filtro) and mesa.liga:
        return True
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    return isinstance(mapa, Mapping) and any(
        isinstance(v, Filtro) and v.liga for v in mapa.values())


def ps_travado_ms(dono: object, uniq: object) -> int:
    """Quanto o PS espera pelo segundo botão do gesto neste controle; zero = desligado."""
    filtro = da_peca(dono, uniq)
    return round(filtro.ps_travado_s * 1000) if filtro is not None else 0


def _estados(dono: object) -> dict[tuple[str, str], FiltroDoControle]:
    valor = getattr(dono, _ATRIBUTO_DOS_ESTADOS, None)
    if not isinstance(valor, dict):
        valor = {}
        setattr(dono, _ATRIBUTO_DOS_ESTADOS, valor)
    return valor


def traduzir(
    dono: object,
    uniq: object,
    botoes: frozenset[str],
    l2: int,
    r2: int,
    agora: float,
    soltos: frozenset[str] = frozenset(),
    espaco: str = "",
) -> tuple[frozenset[str], int, int, frozenset[str]]:
    """O tique do controle ``uniq`` pelo filtro que vale para ele. Sem filtro, passa intacto.

    ``espaco`` separa quem lê o controle por um caminho próprio (a tabela de teclas): cada
    um guarda o SEU estado, e a trava de um não prende o botão do outro.
    """
    filtro = da_peca(dono, uniq)
    if filtro is None or not filtro.liga:
        return botoes, l2, r2, soltos
    estados = _estados(dono)
    estado = estados.setdefault((espaco, chave(uniq)), FiltroDoControle())
    return estado.passo(filtro, botoes, l2, r2, agora, soltos)


def esquecer(dono: object, uniq: object = None, espaco: str | None = None) -> None:
    """Solta o preso: de um controle (``uniq``) ou de todos, num ``espaco`` ou em todos."""
    if dono is None:
        return
    estados = getattr(dono, _ATRIBUTO_DOS_ESTADOS, None)
    if not isinstance(estados, dict):
        return
    alvo = None if uniq is None else chave(uniq)
    # O laço do controle cria estado enquanto o IPC esquece: a lista é uma fotografia e o
    # `pop` tolera quem já saiu.
    for par in list(estados):
        if (alvo is None or par[1] == alvo) and espaco in (None, par[0]):
            estados.pop(par, None)


def preso(dono: object, uniq: object) -> bool:
    """O controle ``uniq`` tem botão travado ou aperto esperando o mínimo? (testes e doctor)"""
    alvo = chave(uniq)
    return any(not e.vazio() for (_, k), e in _estados(dono).items() if k == alvo)


__all__ = [
    "APERTO_MINIMO_DE_FABRICA_MS",
    "CAMPOS",
    "FILTRAVEIS",
    "PS_TRAVADO_DE_FABRICA_MS",
    "REPIQUE_DE_FABRICA_MS",
    "Filtro",
    "FiltroDoControle",
    "alguma",
    "da_peca",
    "definir_ativo",
    "esquecer",
    "montar",
    "preso",
    "ps_travado_ms",
    "traduzir",
]
