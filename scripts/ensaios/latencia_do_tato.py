#!/usr/bin/env python3
"""latencia_do_tato.py — quanto tempo o motor leva para mexer, lido de fora.

A-LATENCIA-DO-TATO-SE-MEDE-SEM-A-MAO-DELA-01 (08/10/2026). Todas as sprints do
tato dependem de um número que ninguém tinha: o intervalo entre a escrita do
relatório e o motor do controle mexer. Sem ele, «sente atrasado» é opinião, e a
única régua era a mão dela. O giroscópio do PRÓPRIO controle, pousado e parado,
lê a vibração do atuador: o instante em que o giro sai do ruído é o instante em
que o motor mexeu.

COMO MEDE
---------
Para cada toque: (1) a linha de base é o giro dos ``JANELA_DO_RUIDO_S`` ANTES da
escrita (centro e dispersão do ruído); (2) o limiar é ``max(piso, média + 6
desvios)`` do ruído, nunca zero; (3) a latência é o instante do primeiro desvio
acima do limiar (dois de três quadros seguidos) MENOS o instante da escrita
DAQUELE toque, dentro da janela que vai até a escrita do toque seguinte. Sem
desvio, o resultado é «nenhum toque lido» (``None``), nunca zero.

O QUE ELE RECUSA (o instrumento que briga com o produto recusa, não anuncia)
----------------------------------------------------------------------------
1. fora do lar de mentira (``HOME`` é o lar real: nada deste instrumento
   precisa do ``~/.config`` dela, e quem roda no lar real migra o perfil dela);
2. o daemon no ar, em QUALQUER socket conhecido — o do ambiente e o do
   ``/run/user/<uid>``, porque num lar de mentira o primeiro engana: ele escreve
   no mesmo hidraw e o relatório dele no meio do ensaio mediria outra coisa;
3. o giro em movimento (rc=3): a linha de base com pico acima de
   ``LIMITE_DE_GIRO_PARADO_GRAUS_S`` é o controle na mão, não pousado.

SEM ``--medir`` não toca em nada: mostra o plano e o que recusaria agora. COM
``--medir`` escreve relatórios de vibração no hidraw indicado (um controle por
vez, cabo ou rádio) e lê o nó «Motion Sensors» dele; ao sair, por qualquer
caminho, manda o relatório de motor zerado.

O QUE A MEDIDA É, E O QUE NÃO É
-------------------------------
O carimbo do giro é o do kernel na CHEGADA do quadro ao computador. No cabo o
quadro chega a cada ~4 ms; no rádio, em rajadas, então a latência do rádio
inclui o intervalo do enlace. É a latência que o JOGO enxerga (do escritor ao
primeiro quadro que mostra o motor), não a do firmware por dentro. O relógio da
escrita é ``time.time()`` imediatamente antes do ``os.write``, o mesmo relógio
(``CLOCK_REALTIME``) do carimbo do evdev. A parte real deste arquivo
(``rodar_no_aparelho``) NÃO foi rodada na árvore de desenvolvimento: o recibo
da tabela em ``docs/protocol/latencia-do-tato.md`` é da bancada.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import os
import pwd
import select
import socket
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
_SRC = _RAIZ / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Quanto giro ANTES da escrita vira a linha de base do ruído.
JANELA_DO_RUIDO_S = 0.200
#: Até onde, depois da escrita, um desvio ainda é daquele toque.
JANELA_DO_TOQUE_S = 0.150
#: Desvios-padrão do ruído acima do centro que contam como toque.
FATOR_DO_RUIDO = 6.0
#: Piso do limiar em graus por segundo: ruído sem dispersão não vira limiar zero.
PISO_DO_LIMIAR_GRAUS_S = 0.5
#: Quadros acima do limiar, entre três seguidos, que confirmam o toque.
CONFIRMAM_DE_TRES = 2
#: Menos que isto de quadros na base e não há ruído medido: não há medição.
MINIMO_DE_QUADROS_NA_BASE = 8
#: Pico do ruído acima disto é o controle na mão, não pousado.
LIMITE_DE_GIRO_PARADO_GRAUS_S = 5.0
#: Força do toque de teste (0..255) nos dois motores.
FORCA_DO_TOQUE = 0xFF
#: Quanto o toque dura antes do relatório de parar.
DURACAO_DO_TOQUE_S = 0.060
#: Silêncio depois de parar, antes do próximo toque (o motor termina de girar).
SILENCIO_ENTRE_TOQUES_S = 0.450

RC_RECUSADO = 2
RC_GIRO_EM_MOVIMENTO = 3
RC_APARELHO = 4


class SemMedicao(Exception):
    """Falta o que se mede (quadros de giro, linha de base): sem número, nunca zero."""


class GiroEmMovimento(SemMedicao):
    """O giro da linha de base tem pico de movimento: o controle não está pousado."""


@dataclass(frozen=True)
class Quadro:
    """Um quadro do giro: instante (s, relógio do kernel) e graus por segundo nos três eixos."""

    t: float
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class LinhaDeBase:
    centro: tuple[float, float, float]
    ruido_medio: float
    desvio: float
    pico: float
    limiar: float


def _desvio_do_centro(q: Quadro, centro: tuple[float, float, float]) -> float:
    return math.sqrt((q.x - centro[0]) ** 2 + (q.y - centro[1]) ** 2 + (q.z - centro[2]) ** 2)


def linha_de_base(quadros: Sequence[Quadro]) -> LinhaDeBase:
    """O ruído do giro parado. Levanta ``SemMedicao`` sem quadros, ``GiroEmMovimento`` em movimento."""
    if len(quadros) < MINIMO_DE_QUADROS_NA_BASE:
        raise SemMedicao(
            f"{len(quadros)} quadro(s) de giro antes da escrita; faltam "
            f"{MINIMO_DE_QUADROS_NA_BASE} para ter ruído medido")
    centro = (
        statistics.median(q.x for q in quadros),
        statistics.median(q.y for q in quadros),
        statistics.median(q.z for q in quadros),
    )
    desvios = [_desvio_do_centro(q, centro) for q in quadros]
    pico = max(desvios)
    if pico > LIMITE_DE_GIRO_PARADO_GRAUS_S:
        raise GiroEmMovimento(
            f"o giro da linha de base chega a {pico:.1f} °/s do centro (limite "
            f"{LIMITE_DE_GIRO_PARADO_GRAUS_S:g}): o controle está em movimento, não pousado")
    media = statistics.fmean(desvios)
    dispersao = statistics.pstdev(desvios)
    limiar = max(PISO_DO_LIMIAR_GRAUS_S, media + FATOR_DO_RUIDO * dispersao)
    return LinhaDeBase(centro, media, dispersao, pico, limiar)


def primeiro_desvio(
    quadros: Sequence[Quadro], base: LinhaDeBase, desde: float, ate: float
) -> float | None:
    """O instante do primeiro quadro de ``(desde, ate)`` acima do limiar, confirmado.

    Confirmado = pelo menos ``CONFIRMAM_DE_TRES`` dos três quadros a partir dele
    acima do limiar: a vibração cruza o zero, e um quadro isolado é ruído.
    """
    janela = [q for q in quadros if desde < q.t < ate]
    acima = [_desvio_do_centro(q, base.centro) > base.limiar for q in janela]
    for i, passou in enumerate(acima):
        if passou and sum(acima[i : i + 3]) >= CONFIRMAM_DE_TRES:
            return janela[i].t
    return None


def latencia_de_um_toque(
    quadros: Sequence[Quadro], escrita: float, proxima_escrita: float | None = None
) -> float | None:
    """Milissegundos da ESCRITA DESTE toque ao primeiro desvio; ``None`` = nenhum toque lido.

    A linha de base é o giro de antes desta escrita. O desvio só vale dentro da
    janela deste toque: depois da escrita do seguinte, é do seguinte.
    """
    base = linha_de_base([q for q in quadros if escrita - JANELA_DO_RUIDO_S <= q.t < escrita])
    fim = escrita + JANELA_DO_TOQUE_S
    if proxima_escrita is not None:
        fim = min(fim, proxima_escrita)
    achado = primeiro_desvio(quadros, base, escrita, fim)
    return None if achado is None else (achado - escrita) * 1000.0


def medir_toques(quadros: Sequence[Quadro], escritas: Sequence[float]) -> list[float | None]:
    """A latência de cada escrita, na ordem; ``None`` onde nenhum toque foi lido."""
    ordem = sorted(escritas)
    return [
        latencia_de_um_toque(quadros, t, ordem[i + 1] if i + 1 < len(ordem) else None)
        for i, t in enumerate(ordem)
    ]


@dataclass(frozen=True)
class Resumo:
    toques: int
    lidos: int
    mediana_ms: float | None
    p95_ms: float | None
    maximo_ms: float | None


def resumir(latencias_ms: Sequence[float | None]) -> Resumo:
    """Mediana, p95 (posto mais próximo) e máximo dos toques lidos."""
    lidas = sorted(v for v in latencias_ms if v is not None)
    if not lidas:
        return Resumo(len(latencias_ms), 0, None, None, None)
    posto = max(1, math.ceil(0.95 * len(lidas)))
    return Resumo(len(latencias_ms), len(lidas), statistics.median(lidas), lidas[posto - 1], lidas[-1])


def _ms(valor: float | None) -> str:
    return "nenhum toque lido" if valor is None else f"{valor:.1f} ms"


def linha_da_tabela(transporte: str, controle: str, resumo: Resumo) -> str:
    return (
        f"| {transporte} | {controle} | {resumo.lidos} de {resumo.toques} | "
        f"{_ms(resumo.mediana_ms)} | {_ms(resumo.p95_ms)} | {_ms(resumo.maximo_ms)} |"
    )


CABECALHO_DA_TABELA = (
    "| transporte | controle | toques lidos | mediana | p95 | máximo |\n"
    "| --- | --- | --- | --- | --- | --- |"
)


# --- as recusas ------------------------------------------------------------------------------


def lar_e_de_mentira(home: str | None, casa_real: str | None) -> bool:
    """``HOME`` existe e não é o lar real de quem roda."""
    if not home or not casa_real:
        return False
    return Path(home).resolve() != Path(casa_real).resolve()


def sockets_do_daemon(env: dict[str, str], uid: int) -> list[Path]:
    """Os sockets onde um daemon pode estar: o do ambiente E o do ``/run/user/<uid>``."""
    nome = env.get("HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "").strip()
    if not nome or "/" in nome:
        nome = (
            "hefesto-dualsense4unix-fake.sock"
            if env.get("HEFESTO_DUALSENSE4UNIX_FAKE") == "1"
            else "hefesto-dualsense4unix.sock"
        )
    pastas: list[Path] = []
    runtime = env.get("XDG_RUNTIME_DIR", "").strip()
    if runtime:
        pastas.append(Path(runtime) / "hefesto-dualsense4unix")
    pastas.append(Path(f"/run/user/{uid}") / "hefesto-dualsense4unix")
    vistos: list[Path] = []
    for pasta in pastas:
        caminho = pasta / nome
        if caminho not in vistos:
            vistos.append(caminho)
    return vistos


def ha_daemon(caminhos: Sequence[Path], espera_s: float = 0.5) -> bool:
    """Algum socket aceita a conexão? Na dúvida, SIM: «não sei» nunca é «parado».

    Socket que não existe, ou que recusa a conexão (o que sobrou de um daemon
    morto), é daemon parado. Quem aceita — ou qualquer outro erro — é «pode
    estar no ar». Só conecta e fecha: nenhuma mensagem vai ao daemon.
    """
    for caminho in caminhos:
        if not caminho.exists():
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
                conexao.settimeout(espera_s)
                conexao.connect(str(caminho))
        except (ConnectionRefusedError, FileNotFoundError):
            continue
        except OSError:
            return True
        return True
    return False


def recusas(env: dict[str, str], uid: int, casa_real: str | None) -> list[str]:
    """Por que o instrumento NÃO roda agora, na ordem; vazio = pode medir."""
    motivos: list[str] = []
    if not lar_e_de_mentira(env.get("HOME"), casa_real):
        motivos.append(
            "HOME é o lar real: rode no lar de mentira da bancada "
            "(docs/process/ferramentas-da-leva/bancada-de-tela-em-lar-de-mentira/)")
    if ha_daemon(sockets_do_daemon(env, uid)):
        motivos.append(
            "há daemon no ar (ou um socket que aceita conexão): ele escreve no mesmo hidraw "
            "e o relatório dele no meio do ensaio mediria outra coisa")
    return motivos


# --- o aparelho (bancada) --------------------------------------------------------------------


def relatorio_de_vibracao(transporte: str, forca: int, seq: int) -> bytes:
    """O relatório de saída que liga (``forca`` > 0) ou desliga os dois motores."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    common = bytearray(rep.COMMON_LEN)
    common[0] = rep.VALID_FLAG0_COMPATIBLE_VIBRATION
    common[2] = forca & 0xFF
    common[3] = forca & 0xFF
    common[38] = rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
    if transporte == "radio":
        return bytes(rep.build_bt_report(common, seq=seq))
    return bytes(rep.build_usb_report(common))


def _coletar(dev: object, ate: float, quadros: list[Quadro], estado: dict[str, float]) -> None:
    """Lê o nó de movimento até o instante ``ate`` e acrescenta os quadros do giro."""
    from evdev import ecodes

    eixos = {ecodes.ABS_RX: "x", ecodes.ABS_RY: "y", ecodes.ABS_RZ: "z"}
    while True:
        falta = ate - time.time()
        if falta <= 0:
            return
        pronto, _, _ = select.select([dev.fd], [], [], min(falta, 0.01))  # type: ignore[attr-defined]
        if not pronto:
            continue
        for ev in dev.read():  # type: ignore[attr-defined]
            if ev.type == ecodes.EV_ABS and ev.code in eixos:
                estado[eixos[ev.code]] = ev.value / estado["res"]
            elif ev.type == ecodes.EV_SYN and ev.code == ecodes.SYN_REPORT:
                quadros.append(Quadro(ev.timestamp(), estado["x"], estado["y"], estado["z"]))


def rodar_no_aparelho(
    transporte: str, hidraw: str, movimento: str, toques: int,
    escrever: Callable[[int, bytes], None] | None = None,
) -> tuple[list[Quadro], list[float]]:
    """Dispara ``toques`` toques de teste e devolve os quadros do giro e as escritas.

    BANCADA: não roda na árvore de desenvolvimento. Escreve no ``hidraw`` e lê o
    nó de movimento; ao sair, por qualquer caminho, manda o relatório zerado.
    """
    from evdev import InputDevice, ecodes

    if str(_AQUI) not in sys.path:
        sys.path.insert(0, str(_AQUI))
    import comum

    dev = InputDevice(movimento)
    os.set_blocking(dev.fd, False)
    resolucao = dev.absinfo(ecodes.ABS_RX).resolution or 1
    estado: dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0, "res": float(resolucao)}
    quadros: list[Quadro] = []
    escritas: list[float] = []
    gravar = escrever or (lambda fd, dados: os.write(fd, dados) and None)
    with comum.abrir_no_hidraw(hidraw, escrita=True) as no:
        seq = 0
        try:
            _coletar(dev, time.time() + JANELA_DO_RUIDO_S * 2, quadros, estado)
            base = linha_de_base(quadros)
            print(f"giro parado: ruído {base.ruido_medio:.2f} °/s, pico {base.pico:.2f}, "
                  f"limiar {base.limiar:.2f} °/s")
            for _ in range(toques):
                _coletar(dev, time.time() + JANELA_DO_RUIDO_S, quadros, estado)
                t = time.time()
                gravar(no.fd, relatorio_de_vibracao(transporte, FORCA_DO_TOQUE, seq))
                escritas.append(t)
                seq = (seq + 1) & 0x0F
                _coletar(dev, t + DURACAO_DO_TOQUE_S, quadros, estado)
                gravar(no.fd, relatorio_de_vibracao(transporte, 0, seq))
                seq = (seq + 1) & 0x0F
                _coletar(dev, time.time() + SILENCIO_ENTRE_TOQUES_S, quadros, estado)
        finally:
            with contextlib.suppress(OSError):
                gravar(no.fd, relatorio_de_vibracao(transporte, 0, seq))
            dev.close()
    return quadros, escritas


# --- a linha de comando ----------------------------------------------------------------------


@dataclass
class Opcoes:
    medir: bool = False
    transporte: str = "cabo"
    controle: str = "P1"
    toques: int = 20
    hidraw: str = ""
    movimento: str = ""
    avisos: list[str] = field(default_factory=list)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Latência do atuador lida pelo giro do próprio controle (sem a mão dela).")
    p.add_argument("--medir", action="store_true",
                   help="escreve toques de teste no --hidraw e lê o --movimento")
    p.add_argument("--transporte", choices=("cabo", "radio"), default="cabo")
    p.add_argument("--controle", default="P1", help="rótulo na tabela: P1 a P4")
    p.add_argument("--toques", type=int, default=20)
    p.add_argument("--hidraw", default="", help="/dev/hidrawN do controle medido")
    p.add_argument("--movimento", default="", help="/dev/input/eventN do «Motion Sensors» DELE")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    env = dict(os.environ)
    motivos = recusas(env, os.getuid(), pwd.getpwuid(os.getuid()).pw_dir)
    print(f"latência do tato — {date.today():%d/%m/%Y} — {args.transporte}, {args.controle}")
    if not args.medir:
        print("SEM --medir: nada vai ao aparelho. Plano: "
              f"{args.toques} toques, giro lido por {JANELA_DO_RUIDO_S * 1000:.0f} ms antes de cada um.")
        print("recusaria agora: " + ("; ".join(motivos) if motivos else "nada"))
        return 0
    if motivos:
        for m in motivos:
            print(f"RECUSADO: {m}")
        return RC_RECUSADO
    if not (args.hidraw and args.movimento):
        print("RECUSADO: --medir pede --hidraw e --movimento do MESMO controle")
        return RC_RECUSADO
    try:
        quadros, escritas = rodar_no_aparelho(
            args.transporte, args.hidraw, args.movimento, args.toques)
        latencias = medir_toques(quadros, escritas)
    except GiroEmMovimento as erro:
        print(f"RECUSADO: {erro}")
        return RC_GIRO_EM_MOVIMENTO
    except (SemMedicao, OSError) as erro:
        print(f"SEM MEDIÇÃO: {erro}")
        return RC_APARELHO
    print(CABECALHO_DA_TABELA)
    print(linha_da_tabela(args.transporte, args.controle, resumir(latencias)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
