#!/usr/bin/env python3
"""o_sinal_em_dois_adaptadores.py — o RSSI do enlace e o da varredura, lado a lado, em dois adaptadores.

O-SINAL-SE-MEDE-EM-DOIS-ADAPTADORES-01 (09/10/2026).

A PERGUNTA
----------
Os limiares do sinal (``radio_da_mesa.SINAL_QUE_ATRASA_DBM`` = -48, ``SINAL_QUE_PERDE_APERTO_DBM``
= -52) saíram de um adaptador só, e o Equilibrar compara o RSSI do ENLACE (``HCI_Read_RSSI``, o
do governador) com o da VARREDURA de outro adaptador (o ``RSSI`` do BlueZ), somando a margem de
``plano_de_radio.MARGEM_DO_SINAL_QUE_COMPENSA_DBM`` (8). As duas réguas nunca foram postas lado a
lado. No BR/EDR o ``HCI_Read_RSSI`` pode ser a distância à faixa ideal do chip (0 dentro dela),
e não dBm: num chip assim, os limiares nunca disparam.

O QUE ELE GRAVA
---------------
Somente leitura do sinal, com o daemon PARADO (a varredura é da central do produto, e instrumento
que briga com o produto recusa). Por segundo, com a hora, o RSSI de cada fonte que existir naquele
instante: a varredura em A, a varredura em B e o enlace em A. Grava o modelo de cada adaptador
(``usb vvvv:pppp``) e o rótulo do controle (P1, P2… pela ordem em que apareceu), nunca o endereço.
Não escreve no controle nem no ``~/.config``; a única ação é a busca (``StartDiscovery``) que ELE
abre nos dois adaptadores e fecha no fim.

As fases (o roteiro exato sai de ``roteiro``):

1. o controle em modo de parear, A e B varrendo: as duas varreduras na mesma régua;
2. o controle conectado em A, no mesmo ponto: o enlace de A contra a varredura de A da fase 1;
3. o controle conectado em A, B varrendo, 2 min a 3 m: quantos segundos B o ouve.

RECUSA
------
Sem ``--medir`` (só descreve o plano); com o daemon no ar; com A igual a B; numa fase fora de 1 a 3;
e, nas fases 2 e 3, sem enlace em A (o controle no cabo não tem rádio: o ensaio nem arma).

USO
---
    o_sinal_em_dois_adaptadores.py roteiro
    o_sinal_em_dois_adaptadores.py gravar --fase 1 --distancia encostado --saida x.jsonl --medir
    o_sinal_em_dois_adaptadores.py resumo x.jsonl
    o_sinal_em_dois_adaptadores.py conferir [x.json]   # as constantes contra os pares gravados

OS INTERRUPTORES (trocar X por Y na bancada sem editar código)
--------------------------------------------------------------
``--a`` / ``HEFESTO_SINAL_A`` e ``--b`` / ``HEFESTO_SINAL_B`` (``hci0``, ``hci1``: trocar A e B é a
repetição do roteiro), ``--segundos`` / ``HEFESTO_SINAL_SEGUNDOS`` (60; 120 na fase 3), ``--nome``
/ ``HEFESTO_SINAL_NOME`` (o nome que a varredura casa, «Wireless Controller»); no resumo e no
conferir, ``--margem`` / ``HEFESTO_SINAL_MARGEM_DBM``, ``--folga`` / ``HEFESTO_SINAL_FOLGA_DBM``,
``--perto`` / ``HEFESTO_SINAL_PERTO_DBM`` (-2: o enlace que lê isto ou mais encostado é a «faixa
ideal») e ``--ouviu`` / ``HEFESTO_SINAL_OUVIU_MINIMO`` (0,1 da fase 3).

As réguas: ``tests/unit/test_o_sinal_se_mede_em_dois_adaptadores.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parents[1]
if str(_RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "src"))

from hefesto_dualsense4unix.integrations import plano_de_radio as pr
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

INSTRUMENTO = "o_sinal_em_dois_adaptadores"
VERSAO = 1
FASES = (1, 2, 3)
DISTANCIAS = ("encostado", "1 m", "3 m com obstáculo", "5 m")
SEGUNDOS = 60.0
SEGUNDOS_DA_FASE_3 = 120.0
NOME_DO_CONTROLE = "Wireless Controller"
#: o enlace que lê isto ou mais com o controle encostado mede a distância à faixa ideal, não dBm
PERTO_DA_FAIXA_IDEAL_DBM = -2.0
#: abaixo desta fração dos segundos da fase 3, o Equilibrar pelo sinal quase não age
OUVIU_MINIMO = 0.1
PARES_GRAVADOS = _RAIZ / "tests" / "fixtures" / INSTRUMENTO / "bancada.json"

RECUSA_SEM_MEDIR = "sem --medir: só descrevo o plano, nada toca"
RECUSA_DAEMON = "o daemon está no ar: a varredura é da central dele, e o ensaio não briga com o produto"
RECUSA_MESMO_ADAPTADOR = "A e B são o mesmo adaptador"
RECUSA_FASE = "a fase é 1, 2 ou 3"
RECUSA_SEM_ENLACE = "o controle não tem enlace em A (no cabo, ou desconectado): o ensaio nem arma"


def _do_ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


# --------------------------------------------------------------- o que se lê


@dataclass(frozen=True)
class Leitura:
    """Um instante: ``varredura`` é ``{"A"|"B": {endereço: dBm}}``; ``enlace``, ``{endereço: dBm}`` em A."""

    varredura: Mapping[str, Mapping[str, int]]
    enlace: Mapping[str, int | None]


@dataclass
class Rotulos:
    """P1, P2… pela ordem em que o controle apareceu. O endereço fica só na memória."""

    _vistos: dict[str, str] = field(default_factory=dict)

    def de(self, endereco: str) -> str:
        chave = endereco.lower()
        if chave not in self._vistos:
            self._vistos[chave] = f"P{len(self._vistos) + 1}"
        return self._vistos[chave]


@dataclass(frozen=True)
class Par:
    """Uma linha gravada: um segundo, um controle, as três fontes. Nenhum endereço."""

    fase: int
    distancia: str
    segundo: int
    hora: str
    modelo_a: str
    modelo_b: str
    controle: str
    varredura_a: int | None
    varredura_b: int | None
    enlace_a: int | None
    #: quantos outros controles têm enlace em A neste segundo (o P2 do roteiro)
    vizinhos: int = 0
    instrumento: str = INSTRUMENTO
    versão: int = VERSAO


def pares_do_instante(
    leitura: Leitura, rotulos: Rotulos, *, fase: int, distancia: str, segundo: int, hora: str,
    modelo_a: str, modelo_b: str,
) -> list[Par]:
    """Os pares deste segundo, um por controle que alguma fonte viu."""
    a = {k.lower(): v for k, v in leitura.varredura.get("A", {}).items()}
    b = {k.lower(): v for k, v in leitura.varredura.get("B", {}).items()}
    enlace = {k.lower(): v for k, v in leitura.enlace.items()}
    vistos = sorted(set(a) | set(b) | set(enlace))
    return [
        Par(fase=fase, distancia=distancia, segundo=segundo, hora=hora, modelo_a=modelo_a,
            modelo_b=modelo_b, controle=rotulos.de(e), varredura_a=a.get(e),
            varredura_b=b.get(e), enlace_a=enlace.get(e),
            vizinhos=max(0, len(enlace) - (1 if e in enlace else 0)))
        for e in vistos
    ]


# --------------------------------------------------------------- as recusas


@dataclass(frozen=True)
class Pedido:
    medir: bool
    fase: int
    a: str
    b: str


def recusas(pedido: Pedido, *, daemon_no_ar: Callable[[], bool]) -> list[str]:
    """As recusas, na ordem do cabeçalho. Lista vazia = pode medir."""
    saida: list[str] = []
    if not pedido.medir:
        saida.append(RECUSA_SEM_MEDIR)
    if pedido.fase not in FASES:
        saida.append(RECUSA_FASE)
    if pedido.a == pedido.b:
        saida.append(RECUSA_MESMO_ADAPTADOR)
    if pedido.medir and daemon_no_ar():
        saida.append(RECUSA_DAEMON)
    return saida


# --------------------------------------------------------------- as portas


@dataclass
class Portas:
    """O que toca o mundo, em dublê nas réguas."""

    daemon_no_ar: Callable[[], bool]
    modelo: Callable[[str], str]
    abrir: Callable[[str, str, int], None]
    ler: Callable[[], Leitura]
    fechar: Callable[[], None]
    dormir: Callable[[float], None] = time.sleep
    hora: Callable[[], str] = lambda: time.strftime("%H:%M:%S")


def daemon_no_ar() -> bool:
    """Na dúvida, SIM: «não sei» nunca é «parado» (a regra dos ensaios do rádio)."""
    import socket

    from hefesto_dualsense4unix.app.ipc_bridge import daemon_status_basic
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    try:
        if daemon_status_basic() is not None:
            return True
        caminho = ipc_socket_path()
        if not caminho.exists():
            return False
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
            conexao.settimeout(1.0)
            conexao.connect(str(caminho))
    except (ConnectionRefusedError, FileNotFoundError):
        return False
    except Exception:
        return True
    return True


def modelo_do_adaptador(hci: str) -> str:
    """``usb vvvv:pppp`` do ``modalias`` do adaptador, sem endereço nenhum."""
    try:
        texto = Path(f"/sys/class/bluetooth/{hci}/device/modalias").read_text().strip()
    except OSError:
        return "não sei"
    if texto.startswith("usb:v") and len(texto) >= 14:
        return f"usb {texto[5:9].lower()}:{texto[10:14].lower()}"
    return texto.split(":", 1)[0] or "não sei"


def portas_de_verdade(nome: str) -> Portas:  # pragma: no cover - a bancada
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
    from hefesto_dualsense4unix.integrations import bluez_dbus

    estado: dict[str, Any] = {}

    def abrir(a: str, b: str, fase: int) -> None:
        barramento = bluez_dbus.BarramentoGio()
        if not barramento.abrir():
            raise RuntimeError(f"o barramento do sistema não abriu: {barramento.erro}")
        dono = bluez_dbus.DonoVivo(barramento)
        if not dono.ligar():
            raise RuntimeError("o BlueZ não respondeu")
        caminhos = {f"/org/bluez/{a}": "A", f"/org/bluez/{b}": "B"}
        # fase 1: A e B varrem; fase 3: só B (o controle está conectado em A); fase 2: ninguém.
        varrer = [c for c, lado in caminhos.items() if fase == 1 or (fase == 3 and lado == "B")]
        for caminho in varrer:
            dono.comecar_busca(caminho, quem=INSTRUMENTO)
        estado.update(dono=dono, barramento=barramento, caminhos=caminhos, varrer=varrer,
                      kernel=ar.LeitorDoKernel(), hci_a=int(a.removeprefix("hci")))

    def ler() -> Leitura:
        dono, caminhos = estado["dono"], estado["caminhos"]
        varredura: dict[str, dict[str, int]] = {"A": {}, "B": {}}
        for aparelho in dono.aparelhos() or ():
            lado = caminhos.get(aparelho.adaptador)
            if lado and aparelho.rssi is not None and nome in (aparelho.nome or ""):
                varredura[lado][aparelho.endereco] = int(aparelho.rssi)
        enlace: dict[str, int | None] = {}
        for conexao in estado["kernel"].conexoes(estado["hci_a"]) or ():
            if conexao.tipo == ar.TIPO_ACL:
                enlace[conexao.endereco] = ar.ler_rssi(estado["hci_a"], conexao.handle)
        return Leitura(varredura=varredura, enlace=enlace)

    def fechar() -> None:
        dono = estado.get("dono")
        if dono is not None:
            for caminho in estado.get("varrer", ()):
                dono.parar_busca(caminho, quem=INSTRUMENTO)
        if estado.get("barramento") is not None:
            estado["barramento"].fechar()

    return Portas(daemon_no_ar=daemon_no_ar, modelo=modelo_do_adaptador, abrir=abrir,
                  ler=ler, fechar=fechar)


# --------------------------------------------------------------- a gravação


def gravar(
    portas: Portas, pedido: Pedido, *, distancia: str, segundos: float, saida: Path,
) -> int:
    """Grava ``segundos`` linhas por controle. Devolve o rc: 0 gravou, 2 recusou."""
    problemas = recusas(pedido, daemon_no_ar=portas.daemon_no_ar)
    if problemas:
        print("RECUSO: " + "; ".join(problemas))
        return 2
    modelo_a, modelo_b = portas.modelo(pedido.a), portas.modelo(pedido.b)
    rotulos = Rotulos()
    portas.abrir(pedido.a, pedido.b, pedido.fase)
    gravados = 0
    try:
        primeira = portas.ler()
        if pedido.fase in (2, 3) and not primeira.enlace:
            print("RECUSO: " + RECUSA_SEM_ENLACE)
            return 2
        saida.parent.mkdir(parents=True, exist_ok=True)
        with saida.open("a", encoding="utf-8") as arquivo:
            for segundo in range(int(segundos)):
                leitura = primeira if segundo == 0 else portas.ler()
                for par in pares_do_instante(
                        leitura, rotulos, fase=pedido.fase, distancia=distancia,
                        segundo=segundo, hora=portas.hora(), modelo_a=modelo_a,
                        modelo_b=modelo_b):
                    arquivo.write(json.dumps(asdict(par), ensure_ascii=False) + "\n")
                    gravados += 1
                portas.dormir(1.0)
    finally:
        portas.fechar()
    print(f"fase {pedido.fase} · {distancia}: {gravados} pares gravados")
    return 0


def ler_pares(caminho: Path) -> list[Par]:
    """Os pares de uma sessão (JSONL) ou de uma tabela gravada (lista JSON)."""
    texto = caminho.read_text(encoding="utf-8").strip()
    brutos = json.loads(texto) if texto.startswith("[") else [
        json.loads(li) for li in texto.splitlines() if li.strip()]
    nomes = set(Par.__dataclass_fields__)
    return [Par(**{k: v for k, v in b.items() if k in nomes}) for b in brutos]


# --------------------------------------------------------------- a conta


def _media(valores: Iterable[float | None]) -> float | None:
    lidos = [float(v) for v in valores if v is not None]
    return statistics.fmean(lidos) if lidos else None


def _desvio(valores: Iterable[float | None]) -> float:
    lidos = [float(v) for v in valores if v is not None]
    return statistics.pstdev(lidos) if len(lidos) > 1 else 0.0


def _correlacao(pares: Sequence[tuple[float, float]]) -> float | None:
    if len(pares) < 3:
        return None
    xs, ys = [p[0] for p in pares], [p[1] for p in pares]
    if statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
        return None
    return statistics.correlation(xs, ys)


@dataclass(frozen=True)
class Distancia:
    """O que uma distância diz, para um modelo de A e um de B."""

    modelo_a: str
    modelo_b: str
    distancia: str
    varredura_a: float | None
    varredura_b: float | None
    #: varredura(B) - varredura(A), nos segundos em que as duas ouviram (fase 1)
    entre_adaptadores: float | None
    ruido: float
    correlacao: float | None
    enlace_a: float | None
    #: enlace(A, fase 2) - varredura(A, fase 1): a conversão de uma régua na outra
    conversao: float | None


def por_distancia(pares: Sequence[Par]) -> list[Distancia]:
    saida: list[Distancia] = []
    chaves = sorted({(p.modelo_a, p.modelo_b, p.distancia) for p in pares if p.fase in (1, 2)},
                    key=lambda k: (k[0], k[1], DISTANCIAS.index(k[2]) if k[2] in DISTANCIAS else 99))
    for ma, mb, d in chaves:
        f1 = [p for p in pares if (p.modelo_a, p.modelo_b, p.distancia, p.fase) == (ma, mb, d, 1)]
        f2 = [p for p in pares if (p.modelo_a, p.modelo_b, p.distancia, p.fase) == (ma, mb, d, 2)]
        lado_a_lado = [(float(p.varredura_a), float(p.varredura_b)) for p in f1
                       if p.varredura_a is not None and p.varredura_b is not None]
        diferencas = [b - a for a, b in lado_a_lado]
        va = _media(p.varredura_a for p in f1)
        ea = _media(p.enlace_a for p in f2)
        saida.append(Distancia(
            modelo_a=ma, modelo_b=mb, distancia=d, varredura_a=va,
            varredura_b=_media(p.varredura_b for p in f1),
            entre_adaptadores=_media(diferencas), ruido=_desvio(diferencas),
            correlacao=_correlacao(lado_a_lado), enlace_a=ea,
            conversao=(ea - va) if ea is not None and va is not None else None))
    return saida


def ouvidos_na_fase_3(pares: Sequence[Par]) -> dict[str, float]:
    """``{modelo de B: fração dos segundos em que B ouviu o controle conectado em A}``."""
    saida: dict[str, float] = {}
    for mb in sorted({p.modelo_b for p in pares if p.fase == 3}):
        dele = [p for p in pares if p.fase == 3 and p.modelo_b == mb and p.enlace_a is not None]
        if dele:
            saida[mb] = sum(1 for p in dele if p.varredura_b is not None) / len(dele)
    return saida


def _br(valor: float | None, casas: int = 1) -> str:
    return "-" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def linhas_curtas(pares: Sequence[Par]) -> list[str]:
    """Uma linha por variável: cada distância, e a fase 3."""
    saida = [
        f"A {d.modelo_a} · B {d.modelo_b} · {d.distancia}: varredura A {_br(d.varredura_a)}, "
        f"B {_br(d.varredura_b)} (B-A {_br(d.entre_adaptadores)} ± {_br(d.ruido)}, "
        f"r {_br(d.correlacao, 2)}), enlace A {_br(d.enlace_a)} (conversão {_br(d.conversao)}) dBm"
        for d in por_distancia(pares)
    ]
    saida += [f"fase 3 · B {mb}: ouviu o controle conectado em {_br(100 * f, 0)}% dos segundos"
              for mb, f in ouvidos_na_fase_3(pares).items()]
    return saida


def conferir(
    pares: Sequence[Par],
    *,
    margem: float = pr.MARGEM_DO_SINAL_QUE_COMPENSA_DBM,
    folga: float = rm.FOLGA_DO_SINAL_DBM,
    perto: float = PERTO_DA_FAIXA_IDEAL_DBM,
) -> list[str]:
    """O que os pares gravados dizem contra as constantes do produto. Lista vazia = confere.

    1. O enlace que lê ``perto`` ou mais com o controle encostado mede a faixa ideal, não dBm: os
       limiares de -48/-52 nunca disparam naquele modelo.
    2. Enlace e varredura que diferem mais que a ``folga`` falam réguas diferentes, e o produto
       compara uma com a outra sem conversão no dono do sinal.
    3. A margem do Equilibrar tem de cobrir a diferença entre os adaptadores e o ruído (2 desvios).
    """
    problemas: list[str] = []
    distancias = por_distancia(pares)
    for modelo in sorted({d.modelo_a for d in distancias}):
        perto_dele = [d.enlace_a for d in distancias
                      if d.modelo_a == modelo and d.distancia == DISTANCIAS[0] and d.enlace_a is not None]
        if perto_dele and max(perto_dele) >= perto:
            problemas.append(
                f"o enlace do modelo {modelo} lê {_br(max(perto_dele))} encostado: é a faixa ideal, "
                f"e os limiares {rm.SINAL_QUE_ATRASA_DBM}/{rm.SINAL_QUE_PERDE_APERTO_DBM} nunca disparam nele")
            continue
        conversoes = [d.conversao for d in distancias if d.modelo_a == modelo and d.conversao is not None]
        media = _media(conversoes)
        if media is not None and abs(media) > folga:
            problemas.append(
                f"o modelo {modelo} lê o enlace {_br(media)} dB longe da varredura: acima da folga de "
                f"{_br(folga, 0)}, e não há conversão no dono do sinal")
    for d in distancias:
        if d.entre_adaptadores is None:
            continue
        precisa = abs(d.entre_adaptadores) + 2 * d.ruido
        if margem < precisa:
            problemas.append(
                f"{d.distancia}: entre A {d.modelo_a} e B {d.modelo_b} a diferença é "
                f"{_br(d.entre_adaptadores)} ± {_br(d.ruido)} dB; a margem de {_br(margem, 0)} não cobre "
                f"{_br(precisa)}")
    return problemas


def gravada(caminho: Path | None = None) -> list[Par] | None:
    """Os pares gravados da bancada, ou ``None`` enquanto ela não rodou."""
    alvo = PARES_GRAVADOS if caminho is None else caminho
    return ler_pares(alvo) if alvo.exists() else None


# --------------------------------------------------------------- o roteiro


def roteiro(a: str, b: str) -> list[str]:
    """O roteiro exato da bancada: as três fases, depois A e B trocados, depois com o P2."""
    script = "scripts/ensaios/o_sinal_em_dois_adaptadores.py"
    saida = ["Pare o daemon antes e religue-o no fim. Marcas no chão: "
             + ", ".join(DISTANCIAS) + "."]
    passo = 0
    for rodada, (x, y, extra) in enumerate(((a, b, ""), (b, a, ""), (a, b, " (com o P2 conectado em A)")), 1):
        saida.append(f"Rodada {rodada}: A = {x}, B = {y}{extra}.")
        for d in DISTANCIAS:
            for fase, gesto in ((1, "controle em modo de parear (PS + Create até piscar)"),
                                (2, "controle conectado em A, no mesmo ponto")):
                passo += 1
                saida.append(f"{passo}. {d}, fase {fase}: {gesto}. {script} gravar --fase {fase} "
                             f"--distancia '{d}' --a {x} --b {y} --saida <sessão>.jsonl --medir")
        passo += 1
        saida.append(f"{passo}. {DISTANCIAS[2]}, fase 3: conectado em A, 2 min. {script} gravar --fase 3 "
                     f"--distancia '{DISTANCIAS[2]}' --a {x} --b {y} --segundos {SEGUNDOS_DA_FASE_3:g} "
                     f"--saida <sessão>.jsonl --medir")
    saida.append(f"Depois: {script} resumo <sessão>.jsonl; e, para a régua, copie a sessão (sem "
                 f"endereço) para tests/fixtures/{INSTRUMENTO}/bancada.json.")
    return saida


def main(argv: Sequence[str] | None = None, portas: Portas | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("roteiro")
    g = sub.add_parser("gravar")
    for alvo in (r, g):
        alvo.add_argument("--a", default=_do_ambiente("HEFESTO_SINAL_A", "hci0"))
        alvo.add_argument("--b", default=_do_ambiente("HEFESTO_SINAL_B", "hci1"))
    g.add_argument("--fase", type=int, required=True)
    g.add_argument("--distancia", required=True)
    g.add_argument("--saida", type=Path, required=True)
    g.add_argument("--medir", action="store_true")
    g.add_argument("--segundos", type=float,
                   default=float(_do_ambiente("HEFESTO_SINAL_SEGUNDOS", "0")) or None)
    g.add_argument("--nome", default=_do_ambiente("HEFESTO_SINAL_NOME", NOME_DO_CONTROLE))
    for nome, ajuda in (("resumo", "os pares de uma sessão"), ("conferir", "as constantes")):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("arquivo", type=Path, nargs="?" if nome == "conferir" else None)
        s.add_argument("--margem", type=float, default=float(_do_ambiente(
            "HEFESTO_SINAL_MARGEM_DBM", str(pr.MARGEM_DO_SINAL_QUE_COMPENSA_DBM))))
        s.add_argument("--folga", type=float, default=float(_do_ambiente(
            "HEFESTO_SINAL_FOLGA_DBM", str(rm.FOLGA_DO_SINAL_DBM))))
        s.add_argument("--perto", type=float, default=float(_do_ambiente(
            "HEFESTO_SINAL_PERTO_DBM", str(PERTO_DA_FAIXA_IDEAL_DBM))))
        s.add_argument("--ouviu", type=float, default=float(_do_ambiente(
            "HEFESTO_SINAL_OUVIU_MINIMO", str(OUVIU_MINIMO))))
    args = p.parse_args(argv)

    if args.comando == "roteiro":
        print("\n".join(roteiro(args.a, args.b)))
        return 0
    if args.comando in ("resumo", "conferir"):
        pares = ler_pares(args.arquivo) if args.arquivo else gravada()
        if pares is None:
            print("sem pares gravados: a bancada ainda não rodou")
            return 0
        if args.comando == "resumo":
            print("\n".join(linhas_curtas(pares)))
        problemas = conferir(pares, margem=args.margem, folga=args.folga, perto=args.perto)
        for mb, fracao in ouvidos_na_fase_3(pares).items():
            if fracao < args.ouviu:
                print(f"nota: B {mb} quase não ouve o controle conectado ({_br(100 * fracao, 0)}%): "
                      "o Equilibrar pelo sinal não age na prática")
        print("\n".join(problemas) or "as constantes conferem com os pares")
        return 1 if (problemas and args.comando == "conferir") else 0
    pedido = Pedido(medir=args.medir, fase=args.fase, a=args.a, b=args.b)
    if portas is None:
        if not args.medir:
            print("RECUSO: " + RECUSA_SEM_MEDIR)
            print(f"o plano: fase {args.fase}, {args.distancia}, A {args.a}, B {args.b}")
            return 2
        portas = portas_de_verdade(args.nome)
    segundos = args.segundos or (SEGUNDOS_DA_FASE_3 if args.fase == 3 else SEGUNDOS)
    return gravar(portas, pedido, distancia=args.distancia, segundos=segundos, saida=args.saida)


if __name__ == "__main__":
    raise SystemExit(main())
