"""faixas_do_ar.py — a régua de 79 canais, UMA FAIXA POR APARELHO (o modelo, sem HTML).

AS-FAIXAS-DIZEM-QUEM-BRIGA-COM-CADA-APARELHO-01 (04/10/2026), o desenho 1 que ela aprovou.
A régua de cima vale para todas as linhas: os mesmos 79 canais, do mesmo tamanho.

* **Pintado é o canal bom**, na cor do aparelho. O buraco é o canal perdido, e nele fica a
  MARCA de quem briga ali: se o aparelho B ocupa a faixa x do aparelho A, nas faixas dos
  DOIS aparece, naquele trecho, a cor do outro (A mostra a cor de B; B mostra a cor de A).
* **O dono do canal perdido sai por atribuição** (nada no HCI nem no vendor lê «quem
  ocupa»): a banda do Wi-Fi conectado em 2,4 GHz, a banda descoberta de um receptor 2.4G,
  e o resto é «ruído sem dono».
* **Ausência é resposta**: aparelho sem mapa lido diz «não se mede agora», e enlace de baixa
  energia (LE) diz «divide o rádio do adaptador dele» — o comando que lê o mapa LE exige
  ``CAP_NET_RAW`` (a tabela do ``hci_sec_filter`` acaba no OGF 5), e este produto não pede root.

Este módulo é puro: entra o que a cena sabe, sai a linha de cada aparelho com as 79 células.
Quem desenha é a aba 08 (``a08_conexoes.html_dos_canais``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial

from hefesto_dualsense4unix.integrations.ar_do_adaptador import (
    CANAIS_DO_BT,
    NIVEL_ENGASGA,
    NIVEL_LISO,
    nivel_dos_canais,
)

#: O dono dos canais que ninguém reivindica.
RUIDO = "ruido"
NOME_DO_RUIDO = "ruído"

BOM = "bom"
PERDIDO = "perdido"
OCUPADO = "ocupado"
LIVRE = "livre"

#: O selo em palavra, pelo MESMO piso do «N/79» do adaptador (``nivel_dos_canais``).
PALAVRA_DO_NIVEL = {NIVEL_LISO: "boa", NIVEL_ENGASGA: "sofrendo"}
PALAVRA_DO_MEIO = "apertada"
NIVEL_DA_PALAVRA = {"boa": "boa", "apertada": "apertada", "sofrendo": "sofrendo"}

DIVIDE_O_RADIO = "divide o rádio do adaptador dele"
NAO_SE_MEDE = "não se mede agora"
FORA_DA_FAIXA = "fora da faixa dos controles"
SEM_REDE = "sem rede conectada"
NAO_DESCOBERTA = "a faixa dele ainda não foi descoberta"


@dataclass(frozen=True)
class Celula:
    """Um dos 79 canais de uma linha. ``dono`` é de quem é o canal PERDIDO (id do ocupante
    ou :data:`RUIDO`); ``marca`` é, num canal OCUPADO, o aparelho que perde ali."""

    canal: int
    estado: str
    dono: str = ""
    marca: str = ""


@dataclass(frozen=True)
class Selo:
    """A palavra do estado (``boa``, ``apertada``, ``sofrendo``, ``nao-atrapalha``…)."""

    nivel: str
    texto: str


@dataclass(frozen=True)
class Linha:
    """A linha de UM aparelho (ou de um rádio da casa) na régua."""

    id: str
    tipo: str
    nome: str
    sub: str = ""
    cor: str = ""
    adaptador: str = ""
    celulas: tuple[Celula, ...] = ()
    sem_faixa: str = ""
    bons: int | None = None
    selo: Selo | None = None
    quem: tuple[tuple[str, str], ...] = ()
    briga: tuple[str, ...] = ()
    qualidade_do_enlace: int | None = None
    rssi: int | None = None
    tira_de: int = 0
    nota: str = ""
    dica: str = ""


@dataclass(frozen=True)
class AparelhoNoAdaptador:
    """Um aparelho conectado a um adaptador, com o que se leu do enlace dele."""

    id: str
    tipo: str
    nome: str
    sub: str = ""
    cor: str = ""
    evitados: frozenset[int] | None = None
    le: bool = False
    qualidade_do_enlace: int | None = None
    rssi: int | None = None


@dataclass(frozen=True)
class Adaptador:
    """Um adaptador Bluetooth: quem está nele e o que ELE evita (``None`` = não se mede)."""

    id: str
    nome: str
    cor: str = ""
    sub: str = ""
    evitados: frozenset[int] | None = None
    aparelhos: tuple[AparelhoNoAdaptador, ...] = ()


@dataclass(frozen=True)
class Ocupante:
    """Quem ocupa uma banda: o Wi-Fi em 2,4 GHz, um receptor 2.4G já descoberto.

    ``banda`` é ``None`` quando não se sabe onde ele mora; ``sem_faixa`` diz por quê, e
    ``selo`` é o estado de saúde que outra leitura (as quedas do Wi-Fi, o receptor) já mediu;
    ``nota`` é a palavra curta que fica ao lado do selo («USB 3.0 + 2.4 GHz») e ``dica`` a
    explicação de uma frase que a tela dá ao passar o mouse nela.
    """

    id: str
    tipo: str
    nome: str
    sub: str = ""
    banda: frozenset[int] | None = None
    sem_faixa: str = ""
    selo: Selo | None = None
    quem: tuple[tuple[str, str], ...] = ()
    nota: str = ""
    dica: str = ""


def banda_do_intervalo(ini: int, fim: int) -> frozenset[int]:
    """Os canais ``ini`` (dentro) a ``fim`` (fora), cortados na régua de 79."""
    return frozenset(range(max(0, int(ini)), min(CANAIS_DO_BT, int(fim))))


def _selo_do_adaptador(bons: int) -> Selo:
    palavra = PALAVRA_DO_NIVEL.get(nivel_dos_canais(bons), PALAVRA_DO_MEIO)
    return Selo(NIVEL_DA_PALAVRA[palavra], f"{palavra} {bons}/{CANAIS_DO_BT}")


def _dono_do_canal(canal: int, ocupantes: Sequence[Ocupante]) -> str:
    for o in ocupantes:
        if o.banda is not None and canal in o.banda:
            return o.id
    return RUIDO


def _nome_do_dono(dono: str, ocupantes: Sequence[Ocupante]) -> str:
    if dono == RUIDO:
        return NOME_DO_RUIDO
    return next((o.nome for o in ocupantes if o.id == dono), dono)


def _tipo_do_dono(dono: str, ocupantes: Sequence[Ocupante]) -> str:
    if dono == RUIDO:
        return RUIDO
    return next((o.tipo for o in ocupantes if o.id == dono), RUIDO)


def _linha_do_aparelho(
    adaptador: Adaptador,
    ap: AparelhoNoAdaptador,
    irmaos: Sequence[AparelhoNoAdaptador],
    ocupantes: Sequence[Ocupante],
) -> Linha:
    linha = partial(Linha, ap.id, ap.tipo, ap.nome, ap.sub, ap.cor, adaptador.id,
                    qualidade_do_enlace=ap.qualidade_do_enlace, rssi=ap.rssi)
    outros = tuple(i.id for i in irmaos if i.id != ap.id)
    if ap.le:
        return linha(sem_faixa=DIVIDE_O_RADIO, briga=outros)
    perdidos = ap.evitados if ap.evitados is not None else adaptador.evitados
    if perdidos is None:
        return linha(sem_faixa=NAO_SE_MEDE, briga=outros)
    celulas = tuple(
        Celula(c, PERDIDO, dono=_dono_do_canal(c, ocupantes)) if c in perdidos
        else Celula(c, BOM)
        for c in range(CANAIS_DO_BT))
    donos = tuple(dict.fromkeys(c.dono for c in celulas if c.estado == PERDIDO))
    bons = CANAIS_DO_BT - len(perdidos)
    return linha(
        celulas=celulas, bons=bons, selo=_selo_do_adaptador(bons),
        quem=tuple((_tipo_do_dono(d, ocupantes), _nome_do_dono(d, ocupantes)) for d in donos),
        briga=tuple(dict.fromkeys((*donos, *outros))))


def linha_do_adaptador(adaptador: Adaptador, ocupantes: Iterable[Ocupante]) -> Linha:
    """A faixa do PRÓPRIO adaptador (o que ele evita), com os donos dos canais perdidos.

    É o que o painel do aparelho no mapa das portas mostra quando o aparelho clicado é o rádio:
    a mesma conta da linha de um aparelho dele, sem o enlace de ninguém.
    """
    como_aparelho = AparelhoNoAdaptador(id=adaptador.id, tipo="adaptador", nome=adaptador.nome,
                                        cor=adaptador.cor)
    return _linha_do_aparelho(adaptador, como_aparelho, (), tuple(ocupantes))


def _selo_de_quem_ocupa(tipo: str, vitimas: int) -> Selo:
    """O Wi-Fi conectado tira canais (a rede anuncia a banda); um receptor 2.4G só «briga
    com»: a banda dele saiu de uma comparação, e a causa nunca é dada como confirmada."""
    if not vitimas:
        return Selo("boa", "não atrapalha")
    if tipo == "wifi":
        return Selo("sofrendo", f"tira canais de {vitimas}")
    return Selo("apertada", f"briga com {vitimas}")


def _linha_do_ocupante(
    o: Ocupante, vitimas_por_canal: Mapping[int, tuple[str, ...]],
    todos: Mapping[str, Linha],
) -> Linha:
    linha = partial(Linha, o.id, o.tipo, o.nome, o.sub, nota=o.nota, dica=o.dica)
    if o.banda is None:
        return linha(sem_faixa=o.sem_faixa, selo=o.selo, quem=o.quem)
    if not o.banda:
        return linha(sem_faixa=o.sem_faixa or FORA_DA_FAIXA,
                     selo=o.selo or Selo("boa", "não atrapalha"), quem=o.quem)
    celulas = tuple(
        Celula(c, OCUPADO, marca=(vitimas_por_canal.get(c) or ("",))[0])
        if c in o.banda else Celula(c, LIVRE)
        for c in range(CANAIS_DO_BT))
    vitimas = tuple(dict.fromkeys(v for c in sorted(o.banda) for v in vitimas_por_canal.get(c, ())))
    donos_de_aparelho = tuple(v for v in vitimas if v in todos)
    selo = o.selo
    if selo is None:
        selo = _selo_de_quem_ocupa(o.tipo, len(donos_de_aparelho))
    return linha(celulas=celulas, selo=selo, quem=o.quem,
                 briga=donos_de_aparelho, tira_de=len(donos_de_aparelho))


@dataclass(frozen=True)
class Regua:
    """A régua inteira: os grupos por adaptador e os outros rádios da casa."""

    grupos: tuple[tuple[Adaptador, tuple[Linha, ...]], ...]
    outros: tuple[Linha, ...]

    def todas(self) -> tuple[Linha, ...]:
        return tuple(linha for _a, linhas in self.grupos for linha in linhas) + self.outros


def montar(adaptadores: Iterable[Adaptador], ocupantes: Iterable[Ocupante]) -> Regua:
    """As linhas de todos os aparelhos, com a briga cruzada nos dois sentidos."""
    ocupantes = tuple(ocupantes)
    adaptadores = tuple(adaptadores)
    grupos = []
    por_id: dict[str, Linha] = {}
    for ad in adaptadores:
        linhas = tuple(_linha_do_aparelho(ad, ap, ad.aparelhos, ocupantes) for ap in ad.aparelhos)
        for linha in linhas:
            por_id[linha.id] = linha
        grupos.append((ad, linhas))
    vitimas: dict[int, list[str]] = {}
    for linha in por_id.values():
        for c in linha.celulas:
            if c.estado == PERDIDO:
                vitimas.setdefault(c.canal, []).append(linha.id)
    vitimas_por_canal = {c: tuple(v) for c, v in vitimas.items()}
    outros = tuple(_linha_do_ocupante(o, vitimas_por_canal, por_id) for o in ocupantes)
    return Regua(grupos=tuple(grupos), outros=outros)


__all__ = [
    "BOM",
    "DIVIDE_O_RADIO",
    "FORA_DA_FAIXA",
    "LIVRE",
    "NAO_DESCOBERTA",
    "NAO_SE_MEDE",
    "NOME_DO_RUIDO",
    "OCUPADO",
    "PERDIDO",
    "RUIDO",
    "SEM_REDE",
    "Adaptador",
    "AparelhoNoAdaptador",
    "Celula",
    "Linha",
    "Ocupante",
    "Regua",
    "Selo",
    "banda_do_intervalo",
    "linha_do_adaptador",
    "montar",
]
