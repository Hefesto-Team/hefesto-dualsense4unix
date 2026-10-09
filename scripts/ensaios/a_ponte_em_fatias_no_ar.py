#!/usr/bin/env python3
"""a_ponte_em_fatias_no_ar.py — quanto a ponte tira do ar de um adaptador, medido por deslocamento.

A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01 (09/10/2026).

A PERGUNTA
----------
Quantas fatias por segundo uma ponte (o ``0x36`` de 93,75 relatórios/s) tira de um
adaptador? O tipo do pacote no ar (3-DH3 de 3 fatias ou 2-DH5 de 5) não se vê pelo
HCI do host; o que se vê é o que a ponte TIRA da entrada, que é elástica e ocupa
todo o ar que sobra. Então o custo sai do deslocamento::

    D(p) = 2 x (soma dos Hz de movimento com 0 pontes - soma com p pontes)

em fatias por segundo, por adaptador (cada relatório de entrada custa 2 fatias,
``radio_da_mesa.FATIAS_POR_RELATORIO_DE_ENTRADA``). Do custo por ponte, ``D(p)/p``,
saem os dois ``k`` candidatos: o do modelo LÍQUIDO (o do mapa do rádio,
``(k - 1) x 93,75``) e o do BRUTO (``(k + 1) x 93,75``). Quem decide qual vale é o
``k`` que cai num pacote que existe (3 ou 5).

O QUE ELE FAZ, NA BANCADA
-------------------------
Roda com o daemon NO AR: a ponte vive nele. Num adaptador escolhido, com os
controles que estiverem nele, sobe 0, 1 e 2 pontes tocando sinal no nó de som de
cada controle (a ponte sob demanda sobe com som), e em cada passo lê, por janela
(30 s, os 5 primeiros descartados): o Hz de movimento de cada controle (o
``state_full``, que vem do evdev e nunca do ``poll.tick``), a entrada e a saída
do adaptador (um ``MedidorDeAr`` PRÓPRIO, ``HCIGETDEVINFO``), o papel mestre de
cada enlace e as pontes que o daemon diz de pé. Antes do primeiro passo ele acha
o sinal mais baixo que mantém a ponte de pé (o silêncio digital não conta: a
bomba não escreve o silêncio), para a carga não ser sensação.

Não escreve nada no controle nem no ``~/.config``. Nenhum endereço sai: o
adaptador é «1», «2» pela ordem do endereço, o controle é «controle 1..4», e o
nome do nó de som nunca é impresso.

RECUSA
------
Sem ``--medir`` (só descreve o plano); com mais pontes que
``radio_da_mesa.N_MAX_PONTES`` (a terceira derrubou os quatro controles em
22/09); com o daemon fora do ar; com jogo aberto; com mais pontes que controles
no adaptador.

USO
---
    a_ponte_em_fatias_no_ar.py medir --adaptador 1 --rotulo "porta direta" --saida x.jsonl --medir
    a_ponte_em_fatias_no_ar.py resumo x.jsonl [--md]
    a_ponte_em_fatias_no_ar.py gravar x.jsonl     # a tabela vira tests/fixtures/.../bancada.json
    a_ponte_em_fatias_no_ar.py conferir           # a constante, o CSV e o desenho seguem a tabela

Gravada a tabela, o ``FATIAS_DA_PONTE``, a procedência da linha do ``k`` no
``docs/data/orcamento-de-ar.csv`` e o ``MARGINAL_DA_PONTE`` do mapa do rádio têm de
dizer o ``k`` que ela mede, e a régua cobra.

OS INTERRUPTORES (trocar X por Y na bancada sem editar código)
--------------------------------------------------------------
``--janela`` / ``HEFESTO_PONTE_JANELA_S`` (30), ``--descarte`` /
``HEFESTO_PONTE_DESCARTE_S`` (5), ``--pontes`` / ``HEFESTO_PONTE_PONTES`` («0,1,2»),
``--sinal`` / ``HEFESTO_PONTE_SINAL_DBFS`` («auto», ou um nível como «-60»), e no
resumo ``--k`` / ``HEFESTO_PONTE_K`` (o ``k`` que a previsão usa; o padrão é o
``FATIAS_DA_PONTE`` do produto) e ``--controles`` / ``HEFESTO_PONTE_CONTROLES`` (4: com
quantos controles no adaptador a última linha conta as pontes que cabem).

As réguas: ``tests/unit/test_a_ponte_se_conta_em_fatias_no_ar.py``.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import os
import re
import statistics
import struct
import subprocess
import sys
import tempfile
import time
import wave
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parents[1]
for _caminho in (str(_AQUI), str(_RAIZ / "src")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

INSTRUMENTO = "a_ponte_em_fatias_no_ar"
VERSAO = 1

JANELA_S = 30.0
DESCARTE_S = 5.0
PONTES_PEDIDAS = (0, 1, 2)
#: os níveis tentados, do mais baixo ao mais alto, para achar o sinal que mantém a
#: ponte de pé; ``None`` é o silêncio digital.
SINAIS_TENTADOS: tuple[float | None, ...] = (None, -60.0, -40.0, -20.0)
ESPERA_DA_PONTE_S = 4.0
#: a janela vale se a ponte pedida esteve de pé em pelo menos esta fração dos segundos
FRACAO_DE_PE = 0.9

#: a tabela da bancada, sem endereço, versionada: é ela que manda no ``FATIAS_DA_PONTE``
TABELA_GRAVADA = _RAIZ / "tests" / "fixtures" / "a_ponte_em_fatias_no_ar" / "bancada.json"
ORCAMENTO = _RAIZ / "docs" / "data" / "orcamento-de-ar.csv"
DESENHO = _RAIZ / "mockup" / "mapa-do-radio.html"
CONSUMIDOR_DO_K = "fatias por relatório de ponte (k)"

RECUSA_SEM_MEDIR = "sem --medir: só descrevo o plano, nada toca"
RECUSA_TRES_PONTES = (
    f"o ensaio para em {rm.N_MAX_PONTES} pontes por adaptador: a terceira derrubou os "
    "quatro controles em 22/09"
)
RECUSA_SEM_DAEMON = "o daemon não respondeu: a ponte vive nele, e sem ele não há o que medir"
RECUSA_JOGO = "há jogo aberto: a medida sairia com o jogo dividindo o ar"
RECUSA_SEM_CONTROLE = "o adaptador escolhido não tem controle no rádio"
RECUSA_MAIS_PONTES_QUE_CONTROLES = "pedi mais pontes que controles neste adaptador"


def _do_ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


def pontes_do_texto(texto: str) -> tuple[int, ...]:
    """«0,1,2» → (0, 1, 2), sem repetição e em ordem."""
    return tuple(sorted({int(p) for p in re.split(r"[,\s]+", texto.strip()) if p}))


def sinal_do_texto(texto: str) -> float | None | str:
    """«auto» → "auto"; «silencio» → None; «-60» → -60.0."""
    limpo = texto.strip().lower()
    if limpo in ("", "auto"):
        return "auto"
    if limpo in ("silencio", "silêncio", "0"):
        return None
    return float(limpo)


# --------------------------------------------------------------------- a conta


@dataclass(frozen=True)
class Janela:
    """Uma janela medida, já sem endereço."""

    adaptador: str
    rotulo: str
    controles: int
    pontes: int
    hz: Mapping[str, float | None]
    acl_rx_por_s: float | None = None
    acl_tx_por_s: float | None = None
    mestre: Mapping[str, bool | None] = field(default_factory=dict)
    pontes_de_pe: float | None = None
    sinal: str = ""
    segundos: float = 0.0
    valida: bool = True
    motivo: str = ""

    @property
    def soma_hz(self) -> float | None:
        valores = list(self.hz.values())
        if not valores or any(v is None for v in valores):
            return None
        return float(sum(v for v in valores if v is not None))

    def linha(self) -> dict[str, Any]:
        return {
            "instrumento": INSTRUMENTO, "versão": VERSAO, "adaptador": self.adaptador,
            "rotulo": self.rotulo, "controles": self.controles, "pontes": self.pontes,
            "hz": dict(self.hz), "acl_rx_por_s": self.acl_rx_por_s,
            "acl_tx_por_s": self.acl_tx_por_s, "mestre": dict(self.mestre),
            "pontes_de_pe": self.pontes_de_pe, "sinal": self.sinal,
            "segundos": self.segundos, "valida": self.valida, "motivo": self.motivo,
        }

    @classmethod
    def da_linha(cls, linha: Mapping[str, Any]) -> Janela:
        return cls(
            adaptador=str(linha["adaptador"]), rotulo=str(linha.get("rotulo") or ""),
            controles=int(linha["controles"]), pontes=int(linha["pontes"]),
            hz={str(k): (None if v is None else float(v)) for k, v in dict(linha["hz"]).items()},
            acl_rx_por_s=_numero(linha.get("acl_rx_por_s")),
            acl_tx_por_s=_numero(linha.get("acl_tx_por_s")),
            mestre=dict(linha.get("mestre") or {}),
            pontes_de_pe=_numero(linha.get("pontes_de_pe")),
            sinal=str(linha.get("sinal") or ""), segundos=float(linha.get("segundos") or 0.0),
            valida=bool(linha.get("valida", True)), motivo=str(linha.get("motivo") or ""),
        )


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor != valor:
        return None
    return float(valor)


def deslocamento(soma_sem_ponte: float, soma_com_pontes: float) -> float:
    """``D(p)``: as fatias por segundo que as pontes tiraram da entrada do adaptador."""
    return rm.FATIAS_POR_RELATORIO_DE_ENTRADA * (soma_sem_ponte - soma_com_pontes)


def k_pelo_modelo_liquido(custo_por_ponte: float) -> float:
    """O ``k`` se a ponte custa ``(k - 1) x 93,75`` (o modelo do mapa do rádio)."""
    return custo_por_ponte / rm.HZ_DA_PONTE + 1


def k_pelo_modelo_bruto(custo_por_ponte: float) -> float:
    """O ``k`` se a ponte custa ``(k + 1) x 93,75`` (o relatório e a resposta inteiros)."""
    return custo_por_ponte / rm.HZ_DA_PONTE - 1


@dataclass(frozen=True)
class LinhaDaTabela:
    """Uma linha da tabela: um adaptador, n controles, p pontes."""

    adaptador: str
    rotulo: str
    controles: int
    pontes: int
    hz_por_controle: float
    entrada_saturada: float
    deslocamento: float | None
    custo_por_ponte: float | None
    k_liquido: float | None
    k_bruto: float | None
    acl_tx_por_s: float | None
    mestre: str


def _media(valores: Iterable[float | None]) -> float | None:
    lidos = [v for v in valores if v is not None]
    return statistics.fmean(lidos) if lidos else None


def tabela(janelas: Sequence[Janela]) -> list[LinhaDaTabela]:
    """As linhas da tabela, só das janelas válidas, agrupadas por (adaptador, controles, pontes)."""
    grupos: dict[tuple[str, int, int], list[Janela]] = {}
    for j in janelas:
        if j.valida and j.soma_hz is not None:
            grupos.setdefault((j.adaptador, j.controles, j.pontes), []).append(j)
    linhas: list[LinhaDaTabela] = []
    for (adaptador, controles, pontes), grupo in sorted(grupos.items()):
        soma = _media(j.soma_hz for j in grupo)
        base = grupos.get((adaptador, controles, 0))
        soma_base = _media(j.soma_hz for j in base) if base else None
        if soma is None or soma_base is None:
            continue
        d = deslocamento(soma_base, soma) if pontes else None
        custo = d / pontes if d is not None and pontes else None
        mestres = [m for j in grupo for m in j.mestre.values() if m is not None]
        linhas.append(LinhaDaTabela(
            adaptador=adaptador, rotulo=grupo[0].rotulo, controles=controles, pontes=pontes,
            hz_por_controle=soma / controles,
            entrada_saturada=rm.FATIAS_POR_RELATORIO_DE_ENTRADA * soma_base,
            deslocamento=d, custo_por_ponte=custo,
            k_liquido=k_pelo_modelo_liquido(custo) if custo is not None else None,
            k_bruto=k_pelo_modelo_bruto(custo) if custo is not None else None,
            acl_tx_por_s=_media(j.acl_tx_por_s for j in grupo),
            mestre=("mestre" if mestres and all(mestres)
                    else "escravo" if mestres and not any(mestres)
                    else "misto" if mestres else "não sei"),
        ))
    return linhas


def _br(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "-"
    return f"{valor:.{casas}f}".replace(".", ",")


def tabela_em_markdown(linhas: Sequence[LinhaDaTabela]) -> str:
    cabecalho = ("| adaptador | controles | pontes | Hz por controle | entrada saturada "
                 "(fatias/s) | D(p) (fatias/s) | custo por ponte | k líquido | k bruto "
                 "| saída (ACL/s) | papel |")
    corpo = [cabecalho, "|" + " --- |" * 11]
    for li in linhas:
        corpo.append(
            f"| {li.adaptador} ({li.rotulo or 'sem rótulo'}) | {li.controles} | {li.pontes} "
            f"| {_br(li.hz_por_controle)} | {_br(li.entrada_saturada)} | {_br(li.deslocamento)} "
            f"| {_br(li.custo_por_ponte)} | {_br(li.k_liquido, 2)} | {_br(li.k_bruto, 2)} "
            f"| {_br(li.acl_tx_por_s)} | {li.mestre} |")
    return "\n".join(corpo)


def previsao_do_hz(entrada_saturada: float, controles: int, pontes: int, k: float) -> float:
    """O Hz por controle que o modelo LÍQUIDO prevê com este ``k``."""
    custo = (k - 1) * rm.HZ_DA_PONTE
    return max(0.0, entrada_saturada - custo * pontes) / rm.FATIAS_POR_RELATORIO_DE_ENTRADA / controles


def linhas_curtas(linhas: Sequence[LinhaDaTabela], k: float) -> list[str]:
    """Uma linha por variável testada: as pontes de cada passo, e o que a medida diz."""
    saida: list[str] = []
    for li in linhas:
        prevista = previsao_do_hz(li.entrada_saturada, li.controles, li.pontes, k)
        if li.pontes == 0:
            saida.append(
                f"adaptador {li.adaptador} · {li.controles} controle(s) · 0 pontes: "
                f"{_br(li.hz_por_controle)} Hz por controle, entrada saturada "
                f"{_br(li.entrada_saturada)} fatias/s")
            continue
        saida.append(
            f"adaptador {li.adaptador} · {li.controles} controle(s) · {li.pontes} ponte(s): "
            f"D = {_br(li.deslocamento)} fatias/s, k = {_br(li.k_liquido, 2)} (líquido) ou "
            f"{_br(li.k_bruto, 2)} (bruto), {_br(li.hz_por_controle)} Hz por controle "
            f"(k = {_br(k, 0)} previa {_br(prevista)})")
    return saida


def pontes_que_cabem(linhas: Sequence[LinhaDaTabela], controles: int) -> dict[str, int]:
    """O ``M`` de cada adaptador medido: quantas pontes deixam ``controles`` em 125 Hz ou mais.

    A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01: a mesma conta do produto
    (``radio_da_mesa.n_max_pela_capacidade``), com o ``C_eff`` (a entrada saturada) e o custo
    por ponte que ESTA tabela mediu em cada adaptador, nunca os do produto.
    """
    saida: dict[str, int] = {}
    for adaptador in sorted({li.adaptador for li in linhas}):
        dele = [li for li in linhas if li.adaptador == adaptador]
        ar = _media(li.entrada_saturada for li in dele)
        custo = _media(li.custo_por_ponte for li in dele if li.pontes)
        if ar is None or custo is None:
            continue
        saida[adaptador] = rm.n_max_pela_capacidade(controles, ar=ar, custo=custo)
    return saida


# --------------------------------------------------------------- as recusas


@dataclass(frozen=True)
class Pedido:
    medir: bool
    adaptador: str
    pontes: tuple[int, ...]


def jogo_do_estado(estado: Mapping[str, Any]) -> bool:
    jogo = estado.get("jogo_steam")
    if not isinstance(jogo, dict):
        return False
    appid = jogo.get("appid")
    return isinstance(appid, int) and not isinstance(appid, bool) and appid > 0


def controles_no_radio(estado: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        c for c in estado.get("controllers") or []
        if isinstance(c, dict) and c.get("transport") == "bt" and c.get("connected", True)
        and c.get("uniq")
    ]


def adaptadores_numerados(estado: Mapping[str, Any]) -> dict[str, str]:
    """``{endereço: "1"}`` pela ordem do endereço; o endereço nunca sai do processo."""
    enderecos = sorted({str(c.get("adaptador") or "").lower()
                        for c in controles_no_radio(estado)} - {""})
    return {e: str(n) for n, e in enumerate(enderecos, start=1)}


def controles_do_adaptador(estado: Mapping[str, Any], numero: str) -> list[str]:
    """Os ``uniq`` dos controles no adaptador de número ``numero``, em ordem estável."""
    numeros = adaptadores_numerados(estado)
    return sorted(
        str(c["uniq"]) for c in controles_no_radio(estado)
        if numeros.get(str(c.get("adaptador") or "").lower()) == numero
    )


def recusas_do_pedido(pedido: Pedido) -> list[str]:
    """O que se recusa sem perguntar nada a ninguém."""
    motivos: list[str] = []
    if not pedido.medir:
        motivos.append(RECUSA_SEM_MEDIR)
    if any(p > rm.N_MAX_PONTES for p in pedido.pontes):
        motivos.append(RECUSA_TRES_PONTES)
    return motivos


def recusas(pedido: Pedido, estado: Mapping[str, Any] | None) -> list[str]:
    """Os motivos para NÃO medir; lista vazia = pode medir."""
    motivos = recusas_do_pedido(pedido)
    if estado is None:
        motivos.append(RECUSA_SEM_DAEMON)
        return motivos
    if jogo_do_estado(estado):
        motivos.append(RECUSA_JOGO)
    controles = controles_do_adaptador(estado, pedido.adaptador)
    if not controles:
        motivos.append(RECUSA_SEM_CONTROLE)
    elif any(p > len(controles) for p in pedido.pontes):
        motivos.append(RECUSA_MAIS_PONTES_QUE_CONTROLES)
    return motivos


# --------------------------------------------------- a constante segue a medida


#: os ``k`` de pacote que carregam o relatório de 403 B: 3-DH3 (3 fatias) e 2-DH5 (5 fatias).
#: Um ``k`` medido longe dos dois diz que o modelo da conta não é o do ar.
PACOTES_DA_PONTE: tuple[int, ...] = (3, 5)
#: quão longe de um pacote o ``k`` medido ainda é aquele pacote
FOLGA_DO_K = 0.5


def k_da_bancada(linhas: Sequence[LinhaDaTabela]) -> tuple[int, str] | None:
    """O ``k`` de pacote que a tabela gravada mede, e o modelo que o explica.

    Primeiro o líquido (o do mapa do rádio), depois o bruto; ``None`` quando nenhum dos dois
    cai perto de um pacote que existe.
    """
    for modelo in ("líquido", "bruto"):
        valores = [li.k_liquido if modelo == "líquido" else li.k_bruto
                   for li in linhas if li.pontes]
        k = _media(valores)
        if k is None:
            return None
        for pacote in PACOTES_DA_PONTE:
            if abs(k - pacote) <= FOLGA_DO_K:
                return pacote, modelo
    return None


def procedencia_do_k(caminho: Path = ORCAMENTO) -> str:
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["consumidor"] == CONSUMIDOR_DO_K:
                return linha["procedencia"].strip()
    return ""


def marginal_do_desenho(caminho: Path = DESENHO) -> float | None:
    achado = re.search(r"const MARGINAL_DA_PONTE = ([\d.]+);", caminho.read_text(encoding="utf-8"))
    return float(achado.group(1)) if achado else None


def conferir_a_constante(
    gravada: Sequence[Janela] | None, *, fatias: float, procedencia: str, marginal: float | None
) -> list[str]:
    """O que destoa entre a tabela gravada da bancada, a constante, o CSV e o desenho.

    Sem tabela gravada, o ``k`` é «provisório» no CSV. Com ela, a constante, o CSV («medido») e o
    ``MARGINAL_DA_PONTE`` do desenho seguem o ``k`` que a tabela mede, e o 3 antigo reprova se a
    medida disser 5.
    """
    if gravada is None:
        if not procedencia.startswith("provisório"):
            return [f"não há tabela gravada da bancada e o CSV diz «{procedencia}» para o k"]
        return []
    medido = k_da_bancada(tabela(gravada))
    if medido is None:
        return ["a tabela gravada não casa com pacote nenhum (3-DH3 ou 2-DH5) em modelo nenhum: "
                "a conta da ponte é outra, e a constante não se escolhe por ela"]
    k, modelo = medido
    problemas: list[str] = []
    if float(fatias) != k:
        problemas.append(f"a bancada mediu k = {k} (modelo {modelo}) e FATIAS_DA_PONTE é {fatias:g}")
    if not procedencia.startswith("medido"):
        problemas.append(f"a bancada mediu e o CSV ainda diz «{procedencia}» para o k")
    if marginal is None or marginal != (k - 1) * rm.HZ_DA_PONTE:
        problemas.append(f"o MARGINAL_DA_PONTE do desenho é {marginal} e o medido dá "
                         f"{(k - 1) * rm.HZ_DA_PONTE:g}")
    return problemas


def gravada(caminho: Path | None = None) -> list[Janela] | None:
    """A tabela que a bancada gravou nas fixtures, ou ``None`` enquanto não houver."""
    alvo = caminho or TABELA_GRAVADA
    return ler_janelas(alvo) if alvo.exists() else None


# ------------------------------------------------------------- a bancada viva


@dataclass
class Portas:
    """O que toca o mundo; nas réguas, tudo dublê."""

    estado: Callable[[], dict[str, Any] | None]
    ar: Callable[[], Mapping[str, Any]]
    tocar: Callable[[str, float | None], Callable[[], None]]
    relogio: Callable[[], float] = time.monotonic
    dormir: Callable[[float], None] = time.sleep
    escrever: Callable[[str], None] = print


def _gerar_wav(caminho: str, dbfs: float | None, segundos: float) -> None:
    """Um seno de 480 Hz no nível pedido (``None`` = silêncio digital), 48 kHz estéreo."""
    taxa = 48_000
    amplitude = 0 if dbfs is None else int(32767 * 10 ** (dbfs / 20))
    periodo = [int(amplitude * math.sin(2 * math.pi * n / 100)) for n in range(100)]
    bloco = b"".join(struct.pack("<hh", a, a) for a in periodo)
    with wave.open(caminho, "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        quadros = int(segundos * taxa)
        repeticoes = max(1, quadros // len(periodo))
        arquivo.writeframes(bloco * repeticoes)


def tocar_no_no(uniq: str, dbfs: float | None, segundos: float) -> Callable[[], None]:
    """Toca o sinal no nó de som do controle; devolve quem para. O nome do nó não sai."""
    from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

    no = nome_do_sink(uniq)
    pasta = tempfile.mkdtemp(prefix="ponte-")
    arquivo = os.path.join(pasta, "sinal.wav")
    _gerar_wav(arquivo, dbfs, segundos)
    processo = subprocess.Popen(
        ["pw-play", "--target", no, arquivo],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    def parar() -> None:
        with contextlib.suppress(Exception):
            processo.terminate()
            processo.wait(timeout=3)
        with contextlib.suppress(OSError):
            os.unlink(arquivo)
            os.rmdir(pasta)

    return parar


def portas_de_verdade(segundos_de_som: float) -> Portas:
    from o_travamento_fator_a_fator import estado_pelo_ipc

    from hefesto_dualsense4unix.integrations.ar_do_adaptador import MedidorDeAr

    medidor = MedidorDeAr()
    return Portas(estado=estado_pelo_ipc, ar=medidor.amostrar,
                  tocar=lambda uniq, dbfs: tocar_no_no(uniq, dbfs, segundos_de_som))


def _de_pe(estado: Mapping[str, Any] | None, uniqs: Sequence[str]) -> int:
    if not estado:
        return 0
    alvo = {u.lower() for u in uniqs}
    return sum(
        1 for c in controles_no_radio(estado)
        if str(c["uniq"]).lower() in alvo and c.get("ponte_do_radio") in rm.MODOS_DA_PONTE
    )


def achar_o_sinal(portas: Portas, uniq: str, pedido: float | None | str) -> float | None | str:
    """O nível mais baixo com que a ponte sobe; ``"nenhum"`` se nenhum a levanta."""
    candidatos = SINAIS_TENTADOS if pedido == "auto" else (pedido,)
    for dbfs in candidatos:
        parar = portas.tocar(uniq, dbfs if not isinstance(dbfs, str) else None)
        try:
            portas.dormir(ESPERA_DA_PONTE_S)
            if _de_pe(portas.estado(), [uniq]) == 1:
                return dbfs
        finally:
            parar()
            portas.dormir(1.0)
    return "nenhum"


def _nome_do_sinal(dbfs: float | None | str) -> str:
    if dbfs is None:
        return "silêncio digital"
    if isinstance(dbfs, str):
        return dbfs
    return f"{dbfs:g} dBFS"


def medir_uma_janela(
    portas: Portas, *, adaptador: str, rotulo: str, uniqs: Sequence[str], pontes: int,
    endereco: str, sinal: str, janela_s: float, descarte_s: float,
) -> Janela:
    """Uma janela: descarta o começo e lê por segundo; a média é o que fica."""
    nomes = {u: f"controle {n}" for n, u in enumerate(uniqs, start=1)}
    portas.dormir(descarte_s)
    hz: dict[str, list[float | None]] = {u: [] for u in uniqs}
    rx: list[float | None] = []
    tx: list[float | None] = []
    de_pe: list[int] = []
    mestre: dict[str, bool | None] = {nomes[u]: None for u in uniqs}
    fim = portas.relogio() + janela_s
    while portas.relogio() < fim:
        estado = portas.estado()
        por_uniq = {str(c["uniq"]).lower(): c for c in controles_no_radio(estado or {})}
        for u in uniqs:
            hz[u].append(_numero((por_uniq.get(u.lower()) or {}).get("hz_movimento")))
        de_pe.append(_de_pe(estado, uniqs))
        ar = portas.ar().get(endereco)
        rx.append(_numero(getattr(ar, "entrada_por_s", None)))
        tx.append(_numero(getattr(ar, "saida_por_s", None)))
        for enlace in ar.conexoes if ar is not None else ():
            dono = str(getattr(enlace, "endereco", "")).replace(":", "").lower()
            for u in uniqs:
                if u.replace(":", "").lower() == dono:
                    mestre[nomes[u]] = bool(getattr(enlace, "mestre", False))
        portas.dormir(1.0)
    medias = {nomes[u]: _media(v) for u, v in hz.items()}
    segundos_de_pe = sum(1 for n in de_pe if n == pontes)
    valida = bool(de_pe) and segundos_de_pe >= FRACAO_DE_PE * len(de_pe)
    motivo = "" if valida else f"a ponte pedida ficou de pé em {segundos_de_pe} de {len(de_pe)} segundos"
    if valida and any(v is None for v in medias.values()):
        valida, motivo = False, "um controle sem Hz de movimento na janela"
    return Janela(
        adaptador=adaptador, rotulo=rotulo, controles=len(uniqs), pontes=pontes, hz=medias,
        acl_rx_por_s=_media(rx), acl_tx_por_s=_media(tx), mestre=mestre,
        pontes_de_pe=_media(float(n) for n in de_pe), sinal=sinal,
        segundos=float(len(de_pe)), valida=valida, motivo=motivo,
    )


def medir(
    portas: Portas, pedido: Pedido, *, rotulo: str, saida: Path, sinal: float | None | str,
    janela_s: float, descarte_s: float,
) -> int:
    estado = portas.estado()
    motivos = recusas(pedido, estado)
    if motivos:
        portas.escrever("RECUSO: " + "; ".join(motivos))
        if RECUSA_SEM_MEDIR in motivos:
            portas.escrever(
                f"o plano: adaptador {pedido.adaptador}, pontes {list(pedido.pontes)}, janelas de "
                f"{janela_s:g} s com {descarte_s:g} s descartados, sinal {sinal}")
        return 2
    assert estado is not None
    uniqs = controles_do_adaptador(estado, pedido.adaptador)
    endereco = next(e for e, n in adaptadores_numerados(estado).items() if n == pedido.adaptador)
    achado = achar_o_sinal(portas, uniqs[0], sinal)
    portas.escrever(f"o sinal que mantém a ponte de pé: {_nome_do_sinal(achado)}")
    if achado == "nenhum":
        portas.escrever("RECUSO: nenhum nível levantou a ponte")
        return 2
    nivel = None if isinstance(achado, str) else achado
    janelas: list[Janela] = []
    for p in pedido.pontes:
        paradas = [portas.tocar(u, nivel) for u in uniqs[:p]]
        try:
            janela = medir_uma_janela(
                portas, adaptador=pedido.adaptador, rotulo=rotulo, uniqs=uniqs, pontes=p,
                endereco=endereco, sinal=_nome_do_sinal(achado), janela_s=janela_s,
                descarte_s=descarte_s)
        finally:
            for parar in paradas:
                parar()
        janelas.append(janela)
        with saida.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(janela.linha(), ensure_ascii=False) + "\n")
        portas.escrever(
            f"pontes {p}: {'válida' if janela.valida else 'fora: ' + janela.motivo}")
    for linha in linhas_curtas(tabela(janelas), rm.FATIAS_DA_PONTE):
        portas.escrever(linha)
    return 0


def ler_janelas(caminho: Path) -> list[Janela]:
    """As janelas de um arquivo: o JSONL que a bancada escreve, ou a lista JSON gravada."""
    texto = caminho.read_text(encoding="utf-8")
    if texto.lstrip().startswith("["):
        brutas = json.loads(texto)
    else:
        brutas = [json.loads(b) for b in texto.splitlines() if b.strip()]
    return [Janela.da_linha(b) for b in brutas if b.get("instrumento") == INSTRUMENTO]


def gravar(origem: Path, destino: Path | None = None) -> Path:
    """Copia as janelas de uma sessão de bancada para a tabela versionada (lista JSON)."""
    alvo = destino or TABELA_GRAVADA
    brutas = [j.linha() for j in ler_janelas(origem)]
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(brutas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return alvo


def main(argv: Sequence[str] | None = None, portas: Portas | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--adaptador", default="1")
    m.add_argument("--rotulo", default="")
    m.add_argument("--saida", type=Path, required=True)
    m.add_argument("--medir", action="store_true")
    m.add_argument("--pontes", default=_do_ambiente("HEFESTO_PONTE_PONTES", "0,1,2"))
    m.add_argument("--janela", type=float,
                   default=float(_do_ambiente("HEFESTO_PONTE_JANELA_S", str(JANELA_S))))
    m.add_argument("--descarte", type=float,
                   default=float(_do_ambiente("HEFESTO_PONTE_DESCARTE_S", str(DESCARTE_S))))
    m.add_argument("--sinal", default=_do_ambiente("HEFESTO_PONTE_SINAL_DBFS", "auto"))
    r = sub.add_parser("resumo")
    r.add_argument("arquivo", type=Path)
    r.add_argument("--md", action="store_true")
    r.add_argument("--k", type=float,
                   default=float(_do_ambiente("HEFESTO_PONTE_K", str(rm.FATIAS_DA_PONTE))))
    r.add_argument("--controles", type=int,
                   default=int(_do_ambiente("HEFESTO_PONTE_CONTROLES", "4")))
    g = sub.add_parser("gravar")
    g.add_argument("arquivo", type=Path)
    sub.add_parser("conferir")
    args = parser.parse_args(argv)

    if args.comando == "resumo":
        linhas = tabela(ler_janelas(args.arquivo))
        if args.md:
            print(tabela_em_markdown(linhas))
        for linha in linhas_curtas(linhas, args.k):
            print(linha)
        for adaptador, cabem in pontes_que_cabem(linhas, args.controles).items():
            print(f"adaptador {adaptador} · {args.controles} controle(s): cabem {cabem} ponte(s) "
                  f"(teto {rm.N_MAX_PONTES})")
        return 0
    if args.comando == "gravar":
        print(f"gravada: {gravar(args.arquivo).relative_to(_RAIZ)}")
        return 0
    if args.comando == "conferir":
        problemas = conferir_a_constante(
            gravada(), fatias=rm.FATIAS_DA_PONTE,
            procedencia=procedencia_do_k(), marginal=marginal_do_desenho())
        for p in problemas:
            print(p)
        print(f"k: {'confere' if not problemas else 'destoa'}")
        return 1 if problemas else 0
    pedido = Pedido(medir=args.medir, adaptador=str(args.adaptador),
                    pontes=pontes_do_texto(args.pontes))
    if portas is None:
        if not args.medir:
            print("RECUSO: " + "; ".join(recusas_do_pedido(pedido)))
            print(f"o plano: adaptador {pedido.adaptador}, pontes {list(pedido.pontes)}, janelas "
                  f"de {args.janela:g} s com {args.descarte:g} s descartados, sinal {args.sinal}")
            return 2
        portas = portas_de_verdade(args.janela + args.descarte + 30.0)
    return medir(portas, pedido, rotulo=args.rotulo, saida=args.saida,
                 sinal=sinal_do_texto(args.sinal), janela_s=args.janela,
                 descarte_s=args.descarte)


if __name__ == "__main__":
    raise SystemExit(main())
