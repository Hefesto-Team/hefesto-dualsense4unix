"""Como o botão ativa: alterna, repete, e entende o toque longo e o duplo.

Dono único e puro: quem chama passa o tempo do laço. Entra logo depois do remapeamento,
nos dois caminhos do pad virtual (o do primeiro controle e o dos outros jogadores) e na
tabela que age com o jogo aberto. O estado é por controle. Um botão tem UM modo: alternar
(um toque segura, outro solta), repetir (segurado, aperta e solta sozinho depois de um
atraso) ou os gestos longo e duplo, que disparam OUTRO botão (o toque curto continua o dele).
O gatilho entra como ``l2``/``r2`` e sai como ``l2_btn``/``r2_btn``, com a força cheia.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from hefesto_dualsense4unix.core.remapeamento_de_botao import (
    FORCA_CHEIA,
    GATILHOS,
    REMAPEAVEIS,
)

#: Os botões que o modo alcança: os mesmos que a troca de botões alcança.
ATIVAVEIS: Final[tuple[str, ...]] = REMAPEAVEIS

#: A partir de quanto curso o gatilho conta como apertado (`uinput_mouse.TRIGGER_PRESS_THRESHOLD`;
#: a régua confere que os dois são o mesmo número).
LIMIAR_DO_GATILHO: Final = 90

#: Quanto dura o aperto que o produto fabrica quando o toque é curto demais para ser segurado.
PULSO_S: Final = 0.06

#: O laço parado por mais que isto esquece o estado: um toque não atravessa um tropeço.
PARADA_S: Final = 1.0

#: Os tempos de fábrica (proposta, a validar pelo usuário) e as faixas que a tela oferece.
LONGO_S: Final = 0.5
DUPLO_S: Final = 0.3
REPETE_APOS_S: Final = 0.5
REPETE_POR_SEGUNDO: Final = 6
FAIXA_DO_LONGO_MS: Final = (150, 3000)
FAIXA_DO_DUPLO_MS: Final = (100, 1000)
FAIXA_DO_ATRASO_MS: Final = (100, 3000)
FAIXA_DA_TAXA: Final = (1, 20)

_ATRIBUTO_DA_MESA: Final = "_ativacao_de_botao_da_mesa"
_ATRIBUTO_POR_PECA: Final = "_ativacao_de_botao_por_peca"
_ATRIBUTO_DOS_ESTADOS: Final = "_ativacao_de_botao_estados"

_VAZIO: Final[Mapping[str, str]] = MappingProxyType({})


@dataclass(frozen=True)
class Ativacao:
    """O que a pessoa escolheu para os botões, já com os tempos em segundos."""

    alternar: frozenset[str] = frozenset()
    repetir: frozenset[str] = frozenset()
    longo: Mapping[str, str] = field(default_factory=lambda: _VAZIO)
    duplo: Mapping[str, str] = field(default_factory=lambda: _VAZIO)
    longo_s: float = LONGO_S
    duplo_s: float = DUPLO_S
    repete_apos_s: float = REPETE_APOS_S
    repete_por_segundo: int = REPETE_POR_SEGUNDO

    @property
    def nomes(self) -> frozenset[str]:
        """Os botões que o modo alcança neste perfil."""
        return self.alternar | self.repetir | frozenset(self.longo) | frozenset(self.duplo)

    @property
    def liga(self) -> bool:
        return bool(self.nomes)


CAMPOS: Final[tuple[str, ...]] = (
    "alternar", "repetir", "longo", "duplo", "longo_ms", "duplo_ms",
    "repete_apos_ms", "repete_por_segundo",
)


#: Os campos da mesma seção que são do filtro (``core/filtro_de_botao``): o botão que trava
#: também conta na regra de um modo só, e as duas camadas juntam a seção do mesmo jeito.
CAMPOS_DO_FILTRO: Final[tuple[str, ...]] = (
    "repique_ms", "aperto_minimo_ms", "travar", "ps_travado_ms")


def recusar(
    alternar: Iterable[str], repetir: Iterable[str],
    longo: Mapping[str, str], duplo: Mapping[str, str],
    travar: Iterable[str] = (),
) -> str | None:
    """Por que estes botões não cabem juntos, ou ``None``: um botão, um modo."""
    conhecidos = set(ATIVAVEIS)
    travar = list(travar)
    nomes = [*alternar, *repetir, *longo, *longo.values(), *duplo, *duplo.values(), *travar]
    fora = sorted({n for n in nomes if n not in conhecidos})
    if fora:
        return f"botão que o modo não alcança: {', '.join(fora)}"
    a, r, t = set(alternar), set(repetir), set(travar)
    g = set(longo) | set(duplo)
    junto = sorted((a & r) | (a & g) | (r & g) | (t & (a | r | g)))
    if junto:
        return f"um botão tem um modo só (alternar, repetir, gesto ou travar): {', '.join(junto)}"
    sozinho = sorted(b for b, d in [*longo.items(), *duplo.items()] if b == d)
    if sozinho:
        return f"o gesto de {sozinho[0]} não pode disparar o próprio {sozinho[0]}"
    return None


def campos_juntos(secao: object, secao_da_peca: object = None) -> dict[str, Any]:
    """A seção do perfil com a da peça por cima campo a campo; se a soma recusa, só a da peça."""
    todos = (*CAMPOS, *CAMPOS_DO_FILTRO)
    da_peca_ = escritos(secao_da_peca, todos)
    campos = {**escritos(secao, todos), **da_peca_}
    if recusar(
        campos.get("alternar") or (), campos.get("repetir") or (),
        campos.get("longo") or {}, campos.get("duplo") or {}, campos.get("travar") or (),
    ):
        return da_peca_
    return campos


def montar(secao: object, secao_da_peca: object = None) -> Ativacao | None:
    """O modo de ativação do perfil, com a seção da peça por cima. ``None`` = sem modo."""
    campos = campos_juntos(secao, secao_da_peca)
    if not campos:
        return None
    ativacao = Ativacao(
        alternar=frozenset(campos.get("alternar") or ()),
        repetir=frozenset(campos.get("repetir") or ()),
        longo=MappingProxyType(dict(campos.get("longo") or {})),
        duplo=MappingProxyType(dict(campos.get("duplo") or {})),
        longo_s=_ms(campos.get("longo_ms"), LONGO_S, FAIXA_DO_LONGO_MS),
        duplo_s=_ms(campos.get("duplo_ms"), DUPLO_S, FAIXA_DO_DUPLO_MS),
        repete_apos_s=_ms(campos.get("repete_apos_ms"), REPETE_APOS_S, FAIXA_DO_ATRASO_MS),
        repete_por_segundo=_taxa(campos.get("repete_por_segundo")),
    )
    return ativacao if ativacao.liga else None


def escritos(secao: object, campos: tuple[str, ...] = CAMPOS) -> dict[str, Any]:
    """Só o que a seção DIZ (quando ela sabe distinguir o escrito do default)."""
    if secao is None:
        return {}
    dito = getattr(secao, "model_fields_set", None)
    nomes = campos if dito is None else tuple(n for n in campos if n in dito)
    return {n: getattr(secao, n) for n in nomes if hasattr(secao, n)}


def _ms(valor: object, padrao: float, faixa: tuple[int, int]) -> float:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return padrao
    return min(max(int(valor), faixa[0]), faixa[1]) / 1000.0


def _taxa(valor: object) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return REPETE_POR_SEGUNDO
    return min(max(int(valor), FAIXA_DA_TAXA[0]), FAIXA_DA_TAXA[1])


@dataclass
class _Botao:
    baixo: bool = False
    desde: float = 0.0
    ligado: bool = False
    segurado: bool = False
    longo: bool = False
    segundo: bool = False
    espera_ate: float | None = None
    pulso_ate: float = float("-inf")
    pulso_nome: str = ""


class AtivacaoDoControle:
    """O estado de UM controle. Mora no dono (o store do daemon), pela identidade dele."""

    __slots__ = ("anterior", "botoes")

    def __init__(self) -> None:
        self.botoes: dict[str, _Botao] = {}
        self.anterior: float | None = None

    def vazio(self) -> bool:
        """Nada preso: nem alternado, nem repetindo, nem esperando o segundo toque."""
        return not any(
            b.ligado or b.baixo or b.espera_ate is not None for b in self.botoes.values())

    def passo(
        self,
        ativacao: Ativacao,
        botoes: frozenset[str],
        l2: int,
        r2: int,
        agora: float,
        soltos: frozenset[str] = frozenset(),
    ) -> tuple[frozenset[str], int, int, frozenset[str]]:
        """Um tique: o que o controle apertou → o que o jogo vai ver.

        Devolve ``(botões, l2, r2, soltos)``. ``soltos`` são os botões apertados e soltos
        entre dois tiques: contam como um toque.
        """
        if self.anterior is not None and agora - self.anterior > PARADA_S:
            self.botoes.clear()
        self.anterior = agora
        nomes = ativacao.nomes
        for velho in [n for n in self.botoes if n not in nomes]:
            del self.botoes[velho]
        if not nomes:
            return botoes, l2, r2, soltos
        forca = {"l2": l2, "r2": r2}
        saida = set(botoes)
        resto = set(soltos)
        quer: dict[str, int] = {}
        for nome in sorted(nomes):
            btn = GATILHOS.get(nome, nome)
            fisico = btn in botoes or nome in botoes or (
                nome in forca and forca[nome] >= LIMIAR_DO_GATILHO)
            toque = btn in soltos or nome in soltos
            saida.discard(btn)
            saida.discard(nome)
            resto.discard(btn)
            resto.discard(nome)
            apertados = self._um(ativacao, nome, fisico, toque, agora)
            for aperto in apertados:
                propria = forca.get(aperto, 0) if aperto == nome else 0
                quer[aperto] = propria if propria >= LIMIAR_DO_GATILHO else FORCA_CHEIA
        for nome in nomes & forca.keys():
            forca[nome] = 0
        for nome, valor in quer.items():
            saida.add(GATILHOS.get(nome, nome))
            if nome in forca:
                forca[nome] = max(forca[nome], valor)
        return frozenset(saida), forca["l2"], forca["r2"], frozenset(resto)

    def _um(
        self, ativacao: Ativacao, nome: str, fisico: bool, toque: bool, agora: float
    ) -> set[str]:
        st = self.botoes.setdefault(nome, _Botao())
        curto = toque and not fisico and not st.baixo
        subiu = (fisico and not st.baixo) or curto
        desceu = (not fisico and st.baixo) or curto
        if subiu:
            st.desde = agora
        st.baixo = fisico
        if nome in ativacao.alternar:
            return self._alternar(st, nome, subiu)
        if nome in ativacao.repetir:
            return self._repetir(ativacao, st, nome, subiu and desceu, agora)
        return self._gesto(ativacao, st, nome, subiu, desceu, agora)

    @staticmethod
    def _alternar(st: _Botao, nome: str, subiu: bool) -> set[str]:
        if subiu:
            st.ligado = not st.ligado
        return {nome} if st.ligado else set()

    @staticmethod
    def _repetir(
        ativacao: Ativacao, st: _Botao, nome: str, toque: bool, agora: float
    ) -> set[str]:
        if toque:
            st.pulso_ate, st.pulso_nome = agora + PULSO_S, nome
        if st.baixo:
            parado = agora - st.desde
            if parado < ativacao.repete_apos_s:
                return {nome}
            periodo = 1.0 / ativacao.repete_por_segundo
            fase = (parado - ativacao.repete_apos_s) % periodo
            return {nome} if fase >= periodo / 2 else set()
        return {st.pulso_nome} if agora < st.pulso_ate else set()

    @staticmethod
    def _gesto(
        ativacao: Ativacao, st: _Botao, nome: str, subiu: bool, desceu: bool, agora: float
    ) -> set[str]:
        longo = ativacao.longo.get(nome)
        duplo = ativacao.duplo.get(nome)
        saida: set[str] = set()
        if st.espera_ate is not None and agora > st.espera_ate:
            st.espera_ate = None
            st.pulso_ate, st.pulso_nome = agora + PULSO_S, nome
        if subiu:
            st.segurado = st.longo = False
            st.segundo = st.espera_ate is not None and duplo is not None
            st.espera_ate = None
        if st.baixo:
            parado = agora - st.desde
            if st.segundo and duplo:
                saida.add(duplo)
            elif longo is not None and parado >= ativacao.longo_s:
                st.longo = True
                saida.add(longo)
            elif longo is None and parado >= ativacao.duplo_s:
                st.segurado = True
                saida.add(nome)
        if desceu:
            if st.segundo and duplo:
                if subiu:
                    st.pulso_ate, st.pulso_nome = agora + PULSO_S, duplo
            elif st.longo or st.segurado:
                pass
            elif duplo is not None:
                st.espera_ate = agora + ativacao.duplo_s
            else:
                st.pulso_ate, st.pulso_nome = agora + PULSO_S, nome
            st.segundo = st.longo = st.segurado = False
        if agora < st.pulso_ate and st.pulso_nome:
            saida.add(st.pulso_nome)
        return saida


def definir_ativo(
    dono: object,
    mesa: Ativacao | None,
    por_peca: Mapping[str, Ativacao | None] | None = None,
) -> None:
    """Guarda o modo ATIVO no dono (o ``StateStore``), e solta tudo o que estava preso."""
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DA_MESA, mesa)
    limpo = {chave(k): v for k, v in (por_peca or {}).items() if chave(k)}
    setattr(dono, _ATRIBUTO_POR_PECA, MappingProxyType(limpo))
    esquecer(dono)


def chave(uniq: object) -> str:
    """A identidade do controle: só os hex, em minúsculas (a mesma do roteador de movimento)."""
    return "".join(c for c in str(uniq or "").lower() if c in "0123456789abcdef")


def da_peca(dono: object, uniq: object) -> Ativacao | None:
    """O modo que vale para o controle ``uniq`` AGORA, ou ``None``."""
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    if isinstance(mapa, Mapping) and uniq:
        k = chave(uniq)
        if k in mapa:
            valor = mapa[k]
            return valor if isinstance(valor, Ativacao) and valor.liga else None
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    return mesa if isinstance(mesa, Ativacao) and mesa.liga else None


def alguma(dono: object) -> bool:
    """Algum controle tem modo neste perfil? Custo de dois ``getattr`` no tique."""
    mesa = getattr(dono, _ATRIBUTO_DA_MESA, None)
    if isinstance(mesa, Ativacao) and mesa.liga:
        return True
    mapa = getattr(dono, _ATRIBUTO_POR_PECA, None)
    return isinstance(mapa, Mapping) and any(
        isinstance(v, Ativacao) and v.liga for v in mapa.values())


def _estados(dono: object) -> dict[tuple[str, str], AtivacaoDoControle]:
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
    """O tique do controle ``uniq`` pelo modo que vale para ele. Sem modo, passa intacto.

    ``espaco`` separa quem lê o controle por um caminho próprio (a tabela de teclas lê os
    botões antes da troca; o pad virtual, depois): cada um guarda o SEU estado.
    """
    ativacao = da_peca(dono, uniq)
    if ativacao is None:
        return botoes, l2, r2, soltos
    estados = _estados(dono)
    estado = estados.setdefault((espaco, chave(uniq)), AtivacaoDoControle())
    return estado.passo(ativacao, botoes, l2, r2, agora, soltos)


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
    """O controle ``uniq`` tem botão alternado, repetindo ou esperando? (testes e doctor)"""
    alvo = chave(uniq)
    return any(
        not estado.vazio() for (_, k), estado in _estados(dono).items() if k == alvo)


__all__ = [
    "ATIVAVEIS",
    "CAMPOS",
    "CAMPOS_DO_FILTRO",
    "DUPLO_S",
    "LIMIAR_DO_GATILHO",
    "LONGO_S",
    "PULSO_S",
    "REPETE_APOS_S",
    "REPETE_POR_SEGUNDO",
    "Ativacao",  # (noqa-acento) identificador ASCII
    "AtivacaoDoControle",
    "alguma",
    "campos_juntos",
    "chave",
    "da_peca",
    "definir_ativo",
    "escritos",
    "esquecer",
    "montar",
    "preso",
    "recusar",
    "traduzir",
]
