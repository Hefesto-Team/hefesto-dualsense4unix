#!/usr/bin/env python3
"""a_ponte_com_dois_quadros.py — a háptica com dois blocos por relatório, às cegas, um controle por vez.

A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01 (09/10/2026), o item 2: a bancada
sensorial do degrau do meio, ANTES de o degrau entrar no produto.

A PERGUNTA
----------
O degrau do meio cede a TAXA da ponte de vibração em vez de cortá-la: metade dos relatórios
(46,875 por segundo em vez de 93,75), cada um com DOIS blocos ``0x12`` de 64 B, a mesma onda
sem buraco. Nenhum projeto público mostra o firmware tocando dois blocos de háptica num
relatório: é suposição inteira. Este ensaio responde duas coisas, com a mão do usuário: o firmware
toca? E a diferença (a latência sobe 10,7 ms) se sente?

O QUE ELE FAZ
-------------
Num controle pelo rádio, ``--rodadas`` rodadas de ``--segundos`` cada, em ordem sorteada (a
``--semente`` repete a ordem). Cada rodada é UM dos dois arranjos, sem dizer qual:

- «um»: o ``0x36`` de hoje, um bloco ``0x12`` por relatório, 93,75 relatórios/s;
- «dois»: o ``0x36`` com dois blocos ``0x12``, 46,875 relatórios/s.

Na tela sai só «rodada N», e ela diz o que sentiu (o que digitar vai ao arquivo). No fim, a
chave (qual rodada foi qual) vai ao ``--saida``, e uma linha curta por rodada.

SEM ``--escrever``, monta os dois arranjos em seco e mostra os blocos e o CRC. COM
``--escrever``, RECUSA nesta ordem: o daemon no ar (ele escreve no mesmo hidraw), sem
``--exigir-mac`` conferido, o controle no cabo, sem ``--eu-estou-sentindo`` (rc=3) e a
bancada tomada (``scripts/bancada.sh exigir``). Nenhum endereço é impresso nem gravado.

OS INTERRUPTORES (trocar X por Y na bancada sem editar código)
--------------------------------------------------------------
``--arranjo`` / ``HEFESTO_DOIS_QUADROS_ARRANJO``: ``cadeia`` (dois blocos ``0x12`` seguidos,
cada um com a sua tag; o padrão) ou ``duplo`` (uma tag com o bit de bloco duplo e 128 B).
``--contador`` / ``HEFESTO_DOIS_QUADROS_CONTADOR``: o contador do ``0x11`` anda ``1`` por
relatório (o padrão) ou ``2`` (um por bloco). ``--rodadas`` / ``HEFESTO_DOIS_QUADROS_RODADAS``
(6), ``--segundos`` / ``HEFESTO_DOIS_QUADROS_SEGUNDOS`` (8), ``--haptica-hz`` /
``HEFESTO_DOIS_QUADROS_HZ`` (120), ``--semente`` / ``HEFESTO_DOIS_QUADROS_SEMENTE``.

As réguas: ``tests/unit/test_a_ponte_se_otimiza_ate_quatro_no_ultra.py``.
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parents[1]
_SRC = str(_RAIZ / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import haptica_bt
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    BLOCO_AUDIO_CONTROL,
    BLOCO_DUPLO,
    BLOCO_HAPTICS,
    BLOCO_SET_STATE,
)

ARRANJO_UM = "um"
ARRANJO_DOIS = "dois"
ARRANJOS_DO_SEGUNDO_BLOCO = ("cadeia", "duplo")
TETO_DE_SEGUNDOS = 30.0
FRACAO_DA_HAPTICA = 0.6


def _do_ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


# --------------------------------------------------------------- o relatório


def onda(haptica_hz: float) -> Callable[[], bytes]:
    """Blocos ``0x12`` de 64 B seguidos de UMA onda: o segundo bloco continua o primeiro."""
    pico = int(FRACAO_DA_HAPTICA * 127)
    fase = [0]

    def _bloco() -> bytes:
        saida = bytearray()
        for _ in range(haptica_bt.AMOSTRAS_POR_CANAL):
            valor = round(pico * math.sin(
                2 * math.pi * haptica_hz * fase[0] / haptica_bt.TAXA_DO_BLOCO))
            fase[0] += 1
            saida += bytes((valor & 0xFF, valor & 0xFF))
        return bytes(saida)

    return _bloco


def montar(
    *,
    seq: int,
    controle: bytes,
    common: bytes,
    blocos: Sequence[bytes],
    arranjo: str = "cadeia",
) -> bytes:
    """O ``0x36`` de háptica com um ou dois blocos ``0x12``, o CRC no lugar. Função pura.

    A cadeia é a do :func:`alto_falante_bt.montar_relatorio_combinado` (``0x11``, ``0x10``,
    ``0x12``), sem o som. Com dois blocos, ``cadeia`` põe duas tags ``0x12`` seguidas e
    ``duplo`` põe uma tag com o bit de bloco duplo e os 128 B juntos.
    """
    if not 1 <= len(blocos) <= 2:
        raise ValueError(f"um ou dois blocos, vieram {len(blocos)}")
    if arranjo not in ARRANJOS_DO_SEGUNDO_BLOCO:
        raise ValueError(f"arranjo {arranjo!r} fora de {ARRANJOS_DO_SEGUNDO_BLOCO}")
    for bloco in blocos:
        if len(bloco) != af.BYTES_DO_BLOCO_HAPTICO:
            raise ValueError(f"o bloco háptico tem {af.BYTES_DO_BLOCO_HAPTICO} B, veio {len(bloco)}")
    if len(controle) != af.BYTES_DO_CONTROLE_035 or len(common) != rep.COMMON_LEN:
        raise ValueError("o 0x11 tem 7 B e o common, 47")
    tamanho = af.TAMANHO_DO_DEGRAU[af.DEGRAU_COMBINADO]
    pkt = bytearray(tamanho)
    pkt[0] = af.DEGRAU_COMBINADO
    pkt[1] = (int(seq) & 0x0F) << 4
    cadeia: list[tuple[int, int, bytes]] = [
        (af.tag_tlv(BLOCO_AUDIO_CONTROL), af.BYTES_DO_CONTROLE_035, controle),
        (af.tag_tlv(BLOCO_SET_STATE), af.LEN_ESTADO_COMBINADO, common),
    ]
    if len(blocos) == 2 and arranjo == "duplo":
        cadeia.append((af.tag_tlv(BLOCO_HAPTICS, duplo=True), af.BYTES_DO_BLOCO_HAPTICO,
                       b"".join(blocos)))
    else:
        cadeia += [(af.tag_tlv(BLOCO_HAPTICS), af.BYTES_DO_BLOCO_HAPTICO, b) for b in blocos]
    pos = af.POS_TAG_CONTROLE_COMBINADO
    for tag, declarado, dados in cadeia:
        pkt[pos] = tag
        pkt[pos + 1] = declarado
        pkt[pos + 2: pos + 2 + len(dados)] = dados
        # o bloco ocupa o que a tag declara (o 0x10 tem 63 B com o common de 47 no começo);
        # o duplo, duas vezes isso.
        pos += 2 + declarado * (2 if tag & BLOCO_DUPLO else 1)
    crc = rep.bt_crc32(pkt[: tamanho - af.CRC_BYTES], seed=rep.BT_CRC_SEED)
    pkt[tamanho - af.CRC_BYTES:] = crc.to_bytes(4, "little")
    return bytes(pkt)


@dataclass
class Escritor:
    """UM escritor por controle: um contador no ``0x11``, uma sequência, uma onda."""

    arranjo_do_bloco: str = "cadeia"
    passo_do_contador: int = 1
    haptica_hz: float = 120.0
    contador: int = 0
    seq: int = 0
    _onda: Callable[[], bytes] | None = None

    def proximo(self, quantos_blocos: int) -> bytes:
        if self._onda is None:
            self._onda = onda(self.haptica_hz)
        relatorio = montar(
            seq=self.seq,
            controle=af.controle_de_audio_035(contador_de_quadros=self.contador),
            common=af.common_de_audio(),
            blocos=[self._onda() for _ in range(quantos_blocos)],
            arranjo=self.arranjo_do_bloco,
        )
        # passo 1: o contador anda um por relatório; passo 2: um por bloco.
        avanco = quantos_blocos if self.passo_do_contador == 2 else 1
        self.contador = (self.contador + avanco) & 0xFF
        self.seq = (self.seq + 1) & 0x0F
        return relatorio


def ritmo_do_arranjo(arranjo: str) -> tuple[int, float]:
    """(blocos por relatório, relatórios por segundo) de cada arranjo da rodada."""
    if arranjo == ARRANJO_UM:
        return 1, rm.HZ_DA_PONTE
    if arranjo == ARRANJO_DOIS:
        return 2, rm.HZ_DA_PONTE_NO_DEGRAU
    raise ValueError(f"arranjo {arranjo!r} fora de ({ARRANJO_UM}, {ARRANJO_DOIS})")


def sortear_rodadas(rodadas: int, semente: int | None) -> list[str]:
    """A ordem cega: metade de cada arranjo (a sobra vai ao «dois»), embaralhada."""
    lista = [ARRANJO_UM] * (rodadas // 2) + [ARRANJO_DOIS] * (rodadas - rodadas // 2)
    random.Random(semente).shuffle(lista)
    return lista


def descrever(relatorio: bytes) -> list[str]:
    """Os blocos da cadeia e o CRC conferido."""
    linhas = [f"id 0x{relatorio[0]:02x}, {len(relatorio)} B, seq {relatorio[1] >> 4}, "
              f"contador {relatorio[af.POS_TAG_CONTROLE_COMBINADO + 2 + 6]}"]
    pos = af.POS_TAG_CONTROLE_COMBINADO
    while pos + 1 < len(relatorio) - af.CRC_BYTES and relatorio[pos]:
        tag, declarado = relatorio[pos], relatorio[pos + 1]
        largura = declarado * (2 if tag & 0x40 else 1)
        linhas.append(f"[{pos:3d}] bloco 0x{tag & 0x3F:02x} (tag 0x{tag:02x}), {largura} B")
        pos += 2 + largura
    crc = rep.bt_crc32(relatorio[: -af.CRC_BYTES], seed=rep.BT_CRC_SEED)
    linhas.append("CRC " + ("certo" if crc.to_bytes(4, "little") == relatorio[-af.CRC_BYTES:]
                            else "ERRADO"))
    return linhas


# --------------------------------------------------------------- o laço


@dataclass
class Contagem:
    """O que o laço contou. Não é a medição: o veredito é do usuário."""

    entregues: int = 0
    recusados_pelo_kernel: int = 0
    segundos: float = 0.0
    erros: list[str] = field(default_factory=list)


def laco(
    proximo: Callable[[], bytes],
    escrever: Callable[[bytes], int],
    *,
    por_segundo: float,
    segundos: float,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> Contagem:
    """Escreve ``por_segundo`` relatórios por segundo durante ``segundos``."""
    contagem = Contagem()
    intervalo = 1.0 / por_segundo
    comeco = alvo = relogio()
    while relogio() - comeco < segundos:
        try:
            escrever(proximo())
            contagem.entregues += 1
        except BlockingIOError:
            contagem.recusados_pelo_kernel += 1
        except OSError as erro:
            contagem.erros.append(str(erro))
            break
        alvo += intervalo
        espera = alvo - relogio()
        if espera > 0:
            dormir(espera)
    contagem.segundos = relogio() - comeco
    return contagem


@dataclass(frozen=True)
class Rodada:
    numero: int
    arranjo: str
    resposta: str
    entregues: int
    por_segundo: float


def rodar(
    ordem: Sequence[str],
    escritor: Escritor,
    escrever: Callable[[bytes], int],
    *,
    segundos: float,
    perguntar: Callable[[str], str],
    avisar: Callable[[str], None] = print,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> list[Rodada]:
    """As rodadas cegas: a tela diz só o número; a resposta de produto vai crua ao arquivo."""
    saida: list[Rodada] = []
    for numero, arranjo in enumerate(ordem, start=1):
        blocos, por_segundo = ritmo_do_arranjo(arranjo)
        avisar(f"rodada {numero}")
        contagem = laco(functools.partial(escritor.proximo, blocos), escrever,
                        por_segundo=por_segundo, segundos=segundos,
                        relogio=relogio, dormir=dormir)
        resposta = perguntar(f"rodada {numero}: o que sentiu? ")
        saida.append(Rodada(numero, arranjo, resposta.strip(), contagem.entregues,
                            round(contagem.entregues / contagem.segundos, 2)
                            if contagem.segundos > 0 else 0.0))
    return saida


def linhas_curtas(rodadas: Sequence[Rodada]) -> list[str]:
    """Uma linha por rodada, a chave aberta: o arranjo, o ritmo entregue e o que o usuário disse."""
    return [f"rodada {r.numero}: {r.arranjo} bloco(s) por relatório, {r.por_segundo:g}/s "
            f"entregues, ela: {r.resposta or '(nada)'}" for r in rodadas]


# --------------------------------------------------------------- a porta


def daemon_no_ar() -> bool:
    """Na dúvida, SIM: «não sei» nunca é «parado» (a regra do ensaio do 0x36)."""
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


def recusa(args: argparse.Namespace, *, daemon: Callable[[], bool] = daemon_no_ar) -> str:
    """A primeira recusa que vale, ou ``""``. A ordem é a do cabeçalho."""
    if daemon():
        return "o daemon está no ar: ele escreve no mesmo hidraw. Ela para o serviço, e roda de novo"
    if not args.exigir_mac:
        return "--escrever exige --exigir-mac com o endereço conferido"
    return ""


def escrever_no_aparelho(args: argparse.Namespace) -> int:
    motivo = recusa(args)
    if motivo:
        print(f"RECUSO: {motivo}")
        return 2
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import controles_na_lista

    alvo = af.so_hex(args.exigir_mac)
    achados = [c for c in controles_na_lista() if af.so_hex(c.uniq) == alvo]
    if not achados:
        print("RECUSO: nenhum controle com esse endereço na lista")
        return 2
    controle = achados[0]
    if controle.transporte != "rádio":
        print("RECUSO: o controle está no cabo; o 0x36 é do rádio")
        return 2
    if not args.eu_estou_sentindo:
        print("PARADO ANTES DE ESCREVER: acrescente --eu-estou-sentindo com a mão dela no controle")
        return 3
    proc = subprocess.run(["bash", str(_RAIZ / "scripts" / "bancada.sh"), "exigir"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print("RECUSO: a bancada está tomada por outra reserva; esperar é a resposta")
        return 2
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import abrir_hidraw_rw

    fd = abrir_hidraw_rw(controle.caminho)
    try:
        rodadas = rodar(
            sortear_rodadas(args.rodadas, args.semente),
            Escritor(args.arranjo, args.contador, args.haptica_hz),
            af.escritor_de_hidraw(fd),
            segundos=min(max(0.0, args.segundos), TETO_DE_SEGUNDOS),
            perguntar=input,
        )
    finally:
        os.close(fd)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        with args.saida.open("a", encoding="utf-8") as f:
            for r in rodadas:
                f.write(json.dumps({**r.__dict__, "arranjo_do_bloco": args.arranjo,
                                    "contador": args.contador, "haptica_hz": args.haptica_hz},
                                   ensure_ascii=False) + "\n")
    for linha in linhas_curtas(rodadas):
        print(linha)
    return 0


def em_seco(args: argparse.Namespace) -> int:
    print(f"EM SECO (nada vai ao aparelho): arranjo {args.arranjo}, contador +{args.contador}, "
          f"onda de {args.haptica_hz:g} Hz")
    escritor = Escritor(args.arranjo, args.contador, args.haptica_hz)
    for arranjo in (ARRANJO_UM, ARRANJO_DOIS):
        blocos, por_segundo = ritmo_do_arranjo(arranjo)
        print(f"{arranjo}: {blocos} bloco(s) por relatório, {por_segundo:g} relatórios/s")
        for linha in descrever(escritor.proximo(blocos)):
            print("  " + linha)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--escrever", action="store_true")
    p.add_argument("--exigir-mac", default="")
    p.add_argument("--eu-estou-sentindo", action="store_true")
    p.add_argument("--arranjo", choices=ARRANJOS_DO_SEGUNDO_BLOCO,
                   default=_do_ambiente("HEFESTO_DOIS_QUADROS_ARRANJO", "cadeia"))
    p.add_argument("--contador", type=int, choices=(1, 2),
                   default=int(_do_ambiente("HEFESTO_DOIS_QUADROS_CONTADOR", "1")))
    p.add_argument("--rodadas", type=int,
                   default=int(_do_ambiente("HEFESTO_DOIS_QUADROS_RODADAS", "6")))
    p.add_argument("--segundos", type=float,
                   default=float(_do_ambiente("HEFESTO_DOIS_QUADROS_SEGUNDOS", "8")))
    p.add_argument("--haptica-hz", type=float,
                   default=float(_do_ambiente("HEFESTO_DOIS_QUADROS_HZ", "120")))
    semente = _do_ambiente("HEFESTO_DOIS_QUADROS_SEMENTE", "")
    p.add_argument("--semente", type=int, default=int(semente) if semente else None)
    p.add_argument("--saida", type=Path, default=None)
    args = p.parse_args(argv)
    return escrever_no_aparelho(args) if args.escrever else em_seco(args)


if __name__ == "__main__":
    raise SystemExit(main())
