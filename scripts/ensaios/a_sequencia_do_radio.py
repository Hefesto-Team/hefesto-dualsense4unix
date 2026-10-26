#!/usr/bin/env python3
"""a_sequencia_do_radio.py — o firmware aceita o 0x31 com o número de sequência repetido ou fora de ordem?

A PERGUNTA (A-SEQUENCIA-DO-RADIO-SE-MEDE-NO-APARELHO-01)
--------------------------------------------------------
O byte 1 do ``0x31`` de saída leva o número de sequência no nibble alto. O SDL manda 0 em todo
report pelo rádio, e o Hefesto carimba um contador por handle. Ninguém tirou o número do envelope
para ver se o firmware joga fora o quadro repetido ou fora de ordem: este instrumento mede.

O DESENHO
---------
Cada caso é uma dupla, e quem diz se o segundo quadro valeu é o próprio aparelho, no byte 47 do
corpo do report de entrada (o efeito ativo do R2, bits 0-3)::

    assentar        R2 desligado, número n - 1     a base
    armar           R2 em modo arma, número n      o byte 47 tem de mudar
    o caso          R2 desligado, número do caso   aceito: volta à base · descartado: fica armado

    repetido        n
    fora de ordem   n - 3
    crc errado      n + 1, com o CRC estragado     o controle negativo: tem de ficar armado

Se o controle negativo voltar à base, o instrumento não distingue aceito de descartado, e o
veredito é ``inconclusivo``.

Porta: o broker (``comum.abrir_no_hidraw``). RECUSA com o daemon no ar: o laço dele escreve
``0x31`` com o contador dele no mesmo enlace. Escreve no aparelho? SIM, só o bloco do R2.

USO
    a_sequencia_do_radio.py --listar
    a_sequencia_do_radio.py --alvo <MAC>
"""

from __future__ import annotations

import argparse
import os
import select
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import RADIO, abrir_no_hidraw, cabecalho_do_instrumento, estado_do_daemon, resumo
from escrita_pelo_broker import (
    alvos_da_mesa,
    common_vazio,
    escolher_alvo,
    linha_do_caderno,
    listar,
    mascarar,
)
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_INPUT_CRC_SEED,
    BT_REPORT_ID,
    BT_REPORT_LEN,
    VALID_FLAG0_RIGHT_TRIGGER_FFB,
    build_bt_report,
    bt_crc32,
)
from hefesto_dualsense4unix.core.trigger_effects import bloco_do_efeito, off, weapon

LINHA_DO_MAPA = "plataforma.escrita_crua@dualsense"
FONTE = "scripts/ensaios/a_sequencia_do_radio.py"
ID_DO_VEREDITO = "sequencia-do-radio-veredito"

COMMON_R2 = 10
OFFSET_DO_EFEITO = 2 + 47
MASCARA_DO_R2 = 0x0F
ESPERA_S = 0.25

ACEITO = "aceito"
DESCARTADO = "descartado"
CEGO = "cego"

OBEDECE = "obedece"
NAO_OBEDECE = "não obedece"
INCONCLUSIVO = "inconclusivo"


@dataclass(frozen=True)
class Caso:
    nome: str
    numero: Callable[[int], int]
    crc_valido: bool = True


REPETIDO = Caso("repetido", lambda n: n)
FORA_DE_ORDEM = Caso("fora de ordem", lambda n: n - 3)
CRC_ERRADO = Caso("crc errado", lambda n: n + 1, crc_valido=False)
CASOS: tuple[Caso, ...] = (CRC_ERRADO, REPETIDO, FORA_DE_ORDEM)


def common_do_r2(armado: bool) -> bytearray:
    """O ``common`` com só o bloco do R2: modo arma ou desligado."""
    common = common_vazio()
    common[0] |= VALID_FLAG0_RIGHT_TRIGGER_FFB
    efeito = weapon(2, 6, 255) if armado else off()
    bloco = bloco_do_efeito(efeito)
    common[COMMON_R2:COMMON_R2 + len(bloco)] = bloco
    return common


def crc_confere(quadro: bytes, *, seed: int | None = None) -> bool:
    """O CRC-32 da cauda bate com o resto do quadro."""
    if len(quadro) != BT_REPORT_LEN:
        return False
    esperado = int.from_bytes(quadro[BT_REPORT_LEN - 4:], "little")
    corpo = quadro[:BT_REPORT_LEN - 4]
    calculado = bt_crc32(corpo) if seed is None else bt_crc32(corpo, seed=seed)
    return calculado == esperado


def quadro(armado: bool, numero: int, *, crc_valido: bool = True) -> bytes:
    """O ``0x31`` de saída com o número pedido; ``crc_valido=False`` estraga o último byte."""
    saida = build_bt_report(common_do_r2(armado), seq=numero & 0x0F)
    if not crc_valido:
        saida[-1] ^= 0xFF
    return bytes(saida)


def numero_de(saida: bytes) -> int:
    return saida[1] >> 4


def efeito_do_r2(report: bytes) -> int | None:
    """O efeito ativo do R2 num ``0x31`` de entrada inteiro e íntegro; ``None`` se não for um."""
    if len(report) != BT_REPORT_LEN or report[0] != BT_REPORT_ID:
        return None
    if not crc_confere(report, seed=BT_INPUT_CRC_SEED):
        return None
    return report[OFFSET_DO_EFEITO] & MASCARA_DO_R2


class Porta(Protocol):
    def escrever(self, saida: bytes) -> None: ...

    def ler_efeito(self, espera: float) -> int | None: ...


@dataclass(frozen=True)
class Resultado:
    caso: str
    numeros: tuple[int, int, int]
    base: int | None
    armado: int | None
    depois: int | None
    crc_do_caso: bool

    @property
    def veredito(self) -> str:
        if self.base is None or self.armado is None or self.depois is None:
            return CEGO
        if self.armado == self.base:
            return CEGO
        if self.depois == self.base:
            return ACEITO
        if self.depois == self.armado:
            return DESCARTADO
        return CEGO


def medir_caso(porta: Porta, caso: Caso, n: int, *, espera: float = ESPERA_S) -> Resultado:
    """Assenta, arma com ``n`` e manda o quadro do caso; o aparelho diz o que valeu."""
    assentar = quadro(False, n - 1)
    armar = quadro(True, n)
    do_caso = quadro(False, caso.numero(n), crc_valido=caso.crc_valido)
    porta.escrever(assentar)
    base = porta.ler_efeito(espera)
    porta.escrever(armar)
    armado = porta.ler_efeito(espera)
    porta.escrever(do_caso)
    depois = porta.ler_efeito(espera)
    return Resultado(
        caso=caso.nome,
        numeros=(numero_de(assentar), numero_de(armar), numero_de(do_caso)),
        base=base,
        armado=armado,
        depois=depois,
        crc_do_caso=crc_confere(do_caso),
    )


def medir(porta: Porta, *, n: int = 7, espera: float = ESPERA_S) -> list[Resultado]:
    """Os três casos, o controle negativo primeiro; o gatilho termina desligado."""
    resultados = [medir_caso(porta, caso, n + 4 * i, espera=espera) for i, caso in enumerate(CASOS)]
    porta.escrever(quadro(False, n + 4 * len(CASOS)))
    return resultados


def veredito(resultados: Sequence[Resultado]) -> str:
    """``obedece`` (o firmware aceita), ``não obedece`` (descarta) ou ``inconclusivo``."""
    por_caso = {r.caso: r for r in resultados}
    negativo = por_caso.get(CRC_ERRADO.nome)
    if negativo is None or negativo.crc_do_caso or negativo.veredito != DESCARTADO:
        return INCONCLUSIVO
    medidos = [por_caso[c.nome].veredito for c in CASOS if c is not CRC_ERRADO and c.nome in por_caso]
    if not medidos or CEGO in medidos:
        return INCONCLUSIVO
    if DESCARTADO in medidos:
        return NAO_OBEDECE
    return OBEDECE


class PortaDoHidraw:
    """O hidraw aberto pelo broker: escreve o quadro e lê o último efeito na janela."""

    def __init__(self, fd: int) -> None:
        self.fd = fd

    def escrever(self, saida: bytes) -> None:
        os.write(self.fd, saida)

    def ler_efeito(self, espera: float) -> int | None:
        fim = time.monotonic() + espera
        ultimo: int | None = None
        while (falta := fim - time.monotonic()) > 0:
            prontos, _, _ = select.select([self.fd], [], [], falta)
            if not prontos:
                break
            efeito = efeito_do_r2(os.read(self.fd, 128))
            if efeito is not None:
                ultimo = efeito
        return ultimo


def linhas_do_caderno(resultados: Sequence[Resultado], transporte: str = "radio") -> list[str]:
    """Uma linha por caso e a do veredito, na ordem do caderno."""
    dia = time.strftime("%d%m")
    linhas = []
    for r in resultados:
        linhas.append(linha_do_caderno(
            id=f"sequencia-do-radio-{r.caso.replace(' ', '-')}-{dia}",
            linha_id=LINHA_DO_MAPA,
            transporte=transporte,
            suspeito="o firmware descarta o 0x31 com o número de sequência repetido ou fora de ordem",
            presente="sim",
            resultado=r.veredito,
            observado_por="aparelho",
            fonte=FONTE,
            nota=(f"números {r.numeros}, crc do caso {'válido' if r.crc_do_caso else 'estragado'}; "
                  f"byte 47 do R2: base {r.base}, armado {r.armado}, depois {r.depois}"),
        ))
    linhas.append(linha_do_caderno(
        id=ID_DO_VEREDITO,
        linha_id=LINHA_DO_MAPA,
        transporte=transporte,
        suspeito="o firmware descarta o 0x31 com o número de sequência repetido ou fora de ordem",
        presente="sim",
        resultado=veredito(resultados),
        observado_por="aparelho",
        fonte=FONTE,
        nota="obedece = aceita o repetido e o fora de ordem; não obedece = descarta",
    ))
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC (inteira ou mascarada) ou nome do hidraw")
    ap.add_argument("--espera", type=float, default=ESPERA_S, help="a janela de leitura de cada quadro")
    args = ap.parse_args()

    pergunta = "o firmware aceita o 0x31 com o número de sequência repetido ou fora de ordem?"
    print(cabecalho_do_instrumento(
        "a_sequencia_do_radio", pergunta,
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
        escreve_no_aparelho=True, daemon_precisa_parar=True))
    aparelhos = alvos_da_mesa()
    if args.listar or not args.alvo:
        print("\ncontroles físicos pelo rádio:")
        print(listar(aparelhos, so_transporte=RADIO))
        return 0
    if estado_do_daemon().rodando:
        print("\nRECUSO: o daemon está no ar e escreve 0x31 com o contador dele no mesmo enlace.")
        return 2
    alvo = escolher_alvo(aparelhos, args.alvo)
    if alvo is None or alvo.transporte != RADIO:
        print(f"alvo {args.alvo!r} não está na mesa pelo rádio.")
        return 1

    no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    print(f"\nalvo ....... {mascarar(alvo.mac)}  ({alvo.caminho_hidraw})")
    print(f"porta ...... {getattr(no, 'linha_de_relatorio', 'broker')}")
    porta = PortaDoHidraw(no.fd)
    try:
        resultados = medir(porta, espera=args.espera)
    finally:
        porta.escrever(quadro(False, 0))
        no.fechar()
    for r in resultados:
        print(f"  {r.caso:<14} números {r.numeros}  base {r.base} armado {r.armado} "
              f"depois {r.depois}  ->  {r.veredito}")
    print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv — quem roda escreve):")
    for linha in linhas_do_caderno(resultados):
        print(linha)
    print(resumo(f"o firmware {veredito(resultados)} ao número repetido e fora de ordem."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
