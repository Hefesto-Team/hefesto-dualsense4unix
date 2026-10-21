"""Como o botão ativa: alterna, repete, e entende o toque longo e o duplo.

Dono único e puro: quem chama passa o tempo do laço. Entra logo depois do remapeamento,
nos dois caminhos do pad virtual (o do primeiro controle e o dos outros jogadores) e na
tabela que age com o jogo aberto. O estado é por controle. Um botão tem UM modo: alternar
(um toque segura, outro solta), repetir (segurado, aperta e solta sozinho depois de um
atraso) ou os gestos longo e duplo, que disparam OUTRO botão (o toque curto continua o dele),
ou a sequência: uma lista de botões com tempos, tocada no pad virtual (e gravada daqui).
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

NOME_DO_GATILHO: Final[Mapping[str, str]] = MappingProxyType(
    {botao: nome for nome, botao in GATILHOS.items()})

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
_ATRIBUTO_DA_GRAVACAO: Final = "_ativacao_de_botao_gravacao"
_ATRIBUTO_DO_TESTE: Final = "_ativacao_de_botao_teste"

#: A sequência: quanto cada botão fica apertado, o menor intervalo entre dois passos (zero
#: continua zero: os dois botões saem juntos), a pausa entre uma volta e a seguinte, o teto de
#: passos e de tempo de uma gravação.
SEGURA_S: Final = 0.04
INTERVALO_MINIMO_S: Final = 0.05
PAUSA_DA_VOLTA_S: Final = 0.1
MAXIMO_DE_PASSOS: Final = 32
MAXIMO_DA_GRAVACAO_S: Final = 30.0
MAXIMO_DO_INTERVALO_MS: Final = 5000

#: Como a sequência toca ao apertar o botão, e a pressa dela (multiplica os intervalos gravados).
JEITOS: Final[tuple[str, ...]] = ("uma_vez", "repete", "alterna")
RITMOS: Final[Mapping[str, float]] = MappingProxyType(
    {"gravado": 1.0, "rapido": 0.5, "devagar": 2.0})

_VAZIO: Final[Mapping[str, str]] = MappingProxyType({})


@dataclass(frozen=True)
class Sequencia:
    """Uma sequência pronta para tocar: cada botão e o instante dele, já na pressa escolhida."""

    passos: tuple[tuple[str, float], ...]
    jeito: str = "uma_vez"

    @property
    def fim(self) -> float:
        """Quando o último botão solta."""
        return (self.passos[-1][1] if self.passos else 0.0) + SEGURA_S

    @property
    def periodo(self) -> float:
        """De uma volta ao começo da seguinte."""
        return self.fim + PAUSA_DA_VOLTA_S


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
    sequencia: Mapping[str, Sequencia] = field(default_factory=dict)

    @property
    def nomes(self) -> frozenset[str]:
        """Os botões que o modo alcança neste perfil."""
        return (self.alternar | self.repetir | frozenset(self.longo) | frozenset(self.duplo)
                | frozenset(self.sequencia))

    @property
    def liga(self) -> bool:
        return bool(self.nomes)


CAMPOS: Final[tuple[str, ...]] = (
    "alternar", "repetir", "longo", "duplo", "longo_ms", "duplo_ms",
    "repete_apos_ms", "repete_por_segundo", "sequencia",
)


#: Os campos da mesma seção que são do filtro (``core/filtro_de_botao``): o botão que trava
#: também conta na regra de um modo só, e as duas camadas juntam a seção do mesmo jeito.
CAMPOS_DO_FILTRO: Final[tuple[str, ...]] = (
    "repique_ms", "aperto_minimo_ms", "travar", "ps_travado_ms")


def recusar(
    alternar: Iterable[str], repetir: Iterable[str],
    longo: Mapping[str, str], duplo: Mapping[str, str],
    travar: Iterable[str] = (),
    sequencia: Mapping[str, Any] | None = None,
) -> str | None:
    """Por que estes botões não cabem juntos, ou ``None``: um botão, um modo."""
    conhecidos = set(ATIVAVEIS)
    travar = list(travar)
    sequencia = sequencia or {}
    passos_da = {b: [p for p, _ in passos_de(v)] for b, v in sequencia.items()}
    nomes = [*alternar, *repetir, *longo, *longo.values(), *duplo, *duplo.values(), *travar,
             *sequencia, *(p for lista in passos_da.values() for p in lista)]
    fora = sorted({n for n in nomes if n not in conhecidos})
    if fora:
        return f"botão que o modo não alcança: {', '.join(fora)}"
    a, r, t = set(alternar), set(repetir), set(travar)
    g = set(longo) | set(duplo)
    q = set(sequencia)
    junto = sorted((a & r) | (a & g) | (r & g) | (t & (a | r | g)) | (q & (a | r | g | t)))
    if junto:
        return ("um botão tem um modo só (alternar, repetir, gesto, travar ou sequência): "
                f"{', '.join(junto)}")
    sozinho = sorted(b for b, d in [*longo.items(), *duplo.items()] if b == d)
    if sozinho:
        return f"o gesto de {sozinho[0]} não pode disparar o próprio {sozinho[0]}"
    vazia = sorted(b for b, lista in passos_da.items() if not lista)
    if vazia:
        return f"a sequência de {vazia[0]} está vazia"
    longa = sorted(b for b, lista in passos_da.items() if len(lista) > MAXIMO_DE_PASSOS)
    if longa:
        return f"a sequência de {longa[0]} passa de {MAXIMO_DE_PASSOS} passos"
    return None


def campos_juntos(secao: object, secao_da_peca: object = None) -> dict[str, Any]:
    """A seção do perfil com a da peça por cima campo a campo; se a soma recusa, só a da peça."""
    todos = (*CAMPOS, *CAMPOS_DO_FILTRO)
    da_peca_ = escritos(secao_da_peca, todos)
    campos = {**escritos(secao, todos), **da_peca_}
    if recusar(
        campos.get("alternar") or (), campos.get("repetir") or (),
        campos.get("longo") or {}, campos.get("duplo") or {}, campos.get("travar") or (),
        campos.get("sequencia") or {},
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
        sequencia=MappingProxyType(
            {b: pronta_para_tocar(v) for b, v in (campos.get("sequencia") or {}).items()}),
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


def _campo(obj: object, nome: str, padrao: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(nome, padrao)
    return getattr(obj, nome, padrao)


def passos_de(sequencia: object) -> list[tuple[str, int]]:
    """Os passos de uma sequência (modelo ou dicionário) como ``[(botão, intervalo_ms)]``."""
    return [(str(_campo(p, "botao", "")), int(_campo(p, "ms", 0) or 0))
            for p in (_campo(sequencia, "passos", None) or ())]


def pronta_para_tocar(sequencia: object) -> Sequencia:
    """A sequência do perfil em instantes: o intervalo vezes a pressa, e o menor intervalo vale."""
    fator = RITMOS.get(str(_campo(sequencia, "ritmo", "gravado")), 1.0)
    jeito = str(_campo(sequencia, "jeito", "uma_vez"))
    quando, agora = [], 0.0
    lista = passos_de(sequencia)
    for i, (botao, ms) in enumerate(lista):
        quando.append((botao, agora))
        if i + 1 < len(lista):
            gap = min(max(ms, 0), MAXIMO_DO_INTERVALO_MS) / 1000.0 * fator
            agora += 0.0 if ms <= 0 else max(gap, INTERVALO_MINIMO_S)
    return Sequencia(tuple(quando), jeito if jeito in JEITOS else "uma_vez")


def sequencia_em_texto(sequencia: object) -> str:
    """``cross:80,circle:120,r1:0|uma_vez|gravado``: a forma que a tela guarda na edição."""
    passos = ",".join(f"{b}:{ms}" for b, ms in passos_de(sequencia))
    jeito, ritmo = _campo(sequencia, "jeito", "uma_vez"), _campo(sequencia, "ritmo", "gravado")
    return f"{passos}|{jeito}|{ritmo}"


def sequencia_do_texto(texto: str) -> dict[str, Any]:
    """O inverso de :func:`sequencia_em_texto`, no formato do perfil."""
    passos_, _, resto = texto.partition("|")
    jeito, _, ritmo = resto.partition("|")
    passos = []
    for item in filter(None, passos_.split(",")):
        botao, _, ms = item.partition(":")
        passos.append({"botao": botao, "ms": int(ms or 0)})
    return {"passos": passos, "jeito": jeito or "uma_vez", "ritmo": ritmo or "gravado"}


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
    volta_desde: float | None = None
    proximo: int = 0
    segurando: list[list[Any]] = field(default_factory=list)


class AtivacaoDoControle:
    """O estado de UM controle. Mora no dono (o store do daemon), pela identidade dele."""

    __slots__ = ("anterior", "botoes")

    def __init__(self) -> None:
        self.botoes: dict[str, _Botao] = {}
        self.anterior: float | None = None

    def vazio(self) -> bool:
        """Nada preso: nem alternado, nem repetindo, nem esperando o segundo toque."""
        return not any(
            b.ligado or b.baixo or b.espera_ate is not None or b.volta_desde is not None
            for b in self.botoes.values())

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
        if nome in ativacao.sequencia:
            return self._sequencia(ativacao.sequencia[nome], st, subiu, agora)
        if nome in ativacao.alternar:
            return self._alternar(st, nome, subiu)
        if nome in ativacao.repetir:
            return self._repetir(ativacao, st, nome, subiu and desceu, agora)
        return self._gesto(ativacao, st, nome, subiu, desceu, agora)

    @staticmethod
    def _sequencia(seq: Sequencia, st: _Botao, subiu: bool, agora: float) -> set[str]:
        """Apertar começa a volta (``alterna`` liga e desliga); a volta começada termina inteira."""
        if subiu:
            if seq.jeito == "alterna":
                st.ligado = not st.ligado
            if st.volta_desde is None and (seq.jeito != "alterna" or st.ligado):
                st.volta_desde, st.proximo, st.segurando = agora, 0, []
        if st.volta_desde is None:
            return set()
        tocando, st.volta_desde, st.proximo = tocar_a_volta(
            seq, st.volta_desde, st.proximo, st.segurando, agora,
            (seq.jeito == "repete" and st.baixo) or (seq.jeito == "alterna" and st.ligado))
        return tocando

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


def tocar_a_volta(
    seq: Sequencia, desde: float, proximo: int, segurando: list[list[Any]], agora: float,
    de_novo: bool,
) -> tuple[set[str], float | None, int]:
    """Um tique de uma volta: os botões apertados agora, quando a volta começou (``None`` = acabou)
    e o próximo passo. Todo botão aparece ao menos num tique, mesmo se o laço atrasar; os passos
    saem na ordem gravada."""
    passou = agora - desde
    while proximo < len(seq.passos) and passou >= seq.passos[proximo][1]:
        botao, quando = seq.passos[proximo]
        segurando.append([botao, quando + SEGURA_S, False])
        proximo += 1
    apertados: set[str] = set()
    for item in list(segurando):
        if not item[2] or passou < item[1]:
            apertados.add(item[0])
        item[2] = True
        if passou >= item[1]:
            segurando.remove(item)
    if proximo >= len(seq.passos) and not segurando and passou >= seq.periodo:
        if not de_novo:
            return apertados, None, 0
        desde = agora if agora - (desde + seq.periodo) > seq.periodo else desde + seq.periodo
        return apertados, desde, 0
    return apertados, desde, proximo


class Gravacao:
    """Uma gravação em curso: cada botão que a mão aperta e o intervalo até o seguinte."""

    __slots__ = ("acabou", "alvo", "anterior", "desde", "toques")

    def __init__(self, alvo: str, agora: float) -> None:
        self.alvo = alvo
        self.desde = agora
        self.anterior: frozenset[str] = frozenset()
        self.toques: list[tuple[str, float]] = []
        self.acabou = False

    def serve(self, uniq: object) -> bool:
        return not self.alvo or self.alvo == chave(uniq)

    def observar(
        self, uniq: object, botoes: frozenset[str], l2: int, r2: int, agora: float,
        soltos: frozenset[str] = frozenset(),
    ) -> None:
        """Um tique: os botões que subiram desde o anterior entram, com o instante deles."""
        if agora - self.desde > MAXIMO_DA_GRAVACAO_S:
            self.acabou = True
            return
        fisicos = {NOME_DO_GATILHO.get(n, n) for n in botoes}
        if l2 >= LIMIAR_DO_GATILHO:
            fisicos.add("l2")
        if r2 >= LIMIAR_DO_GATILHO:
            fisicos.add("r2")
        fisicos &= set(ATIVAVEIS)
        curtos = {NOME_DO_GATILHO.get(n, n) for n in soltos} & set(ATIVAVEIS)
        for botao in sorted((fisicos - self.anterior) | curtos, key=ATIVAVEIS.index):
            if not self.toques and not self.alvo:
                self.alvo = chave(uniq)
            self.toques.append((botao, agora))
        self.anterior = frozenset(fisicos)
        if len(self.toques) >= MAXIMO_DE_PASSOS:
            self.acabou = True

    def passos(self) -> list[dict[str, Any]]:
        """``[{"botao", "ms"}]``: o intervalo de cada botão ao seguinte; o último fica em zero."""
        saida = []
        for i, (botao, t) in enumerate(self.toques):
            ms = 0
            if i + 1 < len(self.toques):
                ms = min(round((self.toques[i + 1][1] - t) * 100) * 10, MAXIMO_DO_INTERVALO_MS)
            saida.append({"botao": botao, "ms": ms})
        return saida


def gravar_iniciar(dono: object, uniq: object, agora: float) -> None:
    """Começa a ouvir o controle ``uniq`` (ou o primeiro que apertar, sem ``uniq``)."""
    if dono is not None:
        setattr(dono, _ATRIBUTO_DA_GRAVACAO, Gravacao(chave(uniq), agora))


def gravar_parar(dono: object) -> list[dict[str, Any]]:
    """Para de ouvir e entrega o que ouviu."""
    g = getattr(dono, _ATRIBUTO_DA_GRAVACAO, None)
    if dono is not None:
        setattr(dono, _ATRIBUTO_DA_GRAVACAO, None)
    return g.passos() if isinstance(g, Gravacao) else []


def gravar_estado(dono: object) -> tuple[bool, list[dict[str, Any]]]:
    """``(ouvindo, passos até agora)``; uma gravação que se encerrou sozinha diz ``False``."""
    g = getattr(dono, _ATRIBUTO_DA_GRAVACAO, None)
    if not isinstance(g, Gravacao):
        return False, []
    return not g.acabou, g.passos()


class Teste:
    """Uma sequência tocada uma vez, sem estar no perfil (o «Tocar para ouvir»)."""

    __slots__ = ("alvo", "desde", "proximo", "segurando", "seq")  # nomes de atributo (noqa-acento)

    def __init__(self, alvo: str, seq: Sequencia, agora: float) -> None:
        self.alvo, self.seq, self.desde = alvo, seq, agora
        self.proximo = 0
        self.segurando: list[list[Any]] = []


def tocar_agora(dono: object, uniq: object, sequencia: object, agora: float) -> None:
    """Toca ``sequencia`` uma vez no pad virtual de ``uniq`` (ou do primeiro que o laço atender)."""
    if dono is None:
        return
    seq = pronta_para_tocar(sequencia)
    setattr(dono, _ATRIBUTO_DO_TESTE, Teste(chave(uniq), Sequencia(seq.passos, "uma_vez"), agora))


def _gravando(dono: object) -> Gravacao | None:
    g = getattr(dono, _ATRIBUTO_DA_GRAVACAO, None)
    return g if isinstance(g, Gravacao) and not g.acabou else None


def _testando(dono: object) -> Teste | None:
    t = getattr(dono, _ATRIBUTO_DO_TESTE, None)
    return t if isinstance(t, Teste) else None


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
    if _gravando(dono) is not None or _testando(dono) is not None:
        return True
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
    if not espaco:
        gravacao = _gravando(dono)
        if gravacao is not None and gravacao.serve(uniq):
            gravacao.observar(uniq, botoes, l2, r2, agora, soltos)
            return frozenset(), 0, 0, frozenset()
    ativacao = da_peca(dono, uniq)
    if ativacao is not None:
        estados = _estados(dono)
        estado = estados.setdefault((espaco, chave(uniq)), AtivacaoDoControle())
        botoes, l2, r2, soltos = estado.passo(ativacao, botoes, l2, r2, agora, soltos)
    teste = _testando(dono) if not espaco else None
    if teste is not None and (not teste.alvo or teste.alvo == chave(uniq)):
        apertados, desde, teste.proximo = tocar_a_volta(
            teste.seq, teste.desde, teste.proximo, teste.segurando, agora, False)
        if desde is None:
            setattr(dono, _ATRIBUTO_DO_TESTE, None)
        else:
            teste.desde = desde
        if apertados:
            botoes = botoes | {GATILHOS.get(n, n) for n in apertados}
            l2 = FORCA_CHEIA if "l2" in apertados else l2
            r2 = FORCA_CHEIA if "r2" in apertados else r2
            botoes = frozenset(botoes)
    return botoes, l2, r2, soltos


def esquecer(dono: object, uniq: object = None, espaco: str | None = None) -> None:
    """Solta o preso: de um controle (``uniq``) ou de todos, num ``espaco`` ou em todos."""
    if dono is None:
        return
    if uniq is None and espaco is None:
        setattr(dono, _ATRIBUTO_DO_TESTE, None)
        setattr(dono, _ATRIBUTO_DA_GRAVACAO, None)
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
    "JEITOS",
    "LIMIAR_DO_GATILHO",
    "LONGO_S",
    "PULSO_S",
    "REPETE_APOS_S",
    "REPETE_POR_SEGUNDO",
    "RITMOS",
    "Ativacao",  # nome da classe (noqa-acento)
    "AtivacaoDoControle",
    "Gravacao",
    "Sequencia",
    "Teste",
    "alguma",
    "campos_juntos",
    "chave",
    "da_peca",
    "definir_ativo",
    "escritos",
    "esquecer",
    "gravar_estado",
    "gravar_iniciar",
    "gravar_parar",
    "montar",
    "passos_de",
    "preso",
    "pronta_para_tocar",
    "recusar",
    "sequencia_do_texto",
    "sequencia_em_texto",
    "tocar_a_volta",
    "tocar_agora",
    "traduzir",
]
