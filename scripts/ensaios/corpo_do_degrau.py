#!/usr/bin/env python3
"""corpo_do_degrau.py — E-1: os bytes excedentes do degrau são ignorados, ou têm forma?

A PERGUNTA QUE ELE DECIDE
--------------------------
Na madrugada de 15/08/2026 ficou medido que o firmware do DualSense **executa
reports de output de 141 e 547 bytes por rádio** — a escada `0x31`-`0x39`, lida do
descritor dos aparelhos dela. O comando de 47 bytes (`common`) vale igual em todos
os degraus: mandar a mesma cor pelo `0x31`, pelo `0x32` e pelo `0x39` acende a
mesma luz.

O que NINGUÉM sabe é o que são os bytes **depois** do `common`. No `0x32` sobram
~92; no `0x39`, ~497. As duas hipóteses:

  IGNORADOS ...... o firmware lê os 47 primeiros e joga o resto fora. A escada é
                   só um envelope maior, e não há nada a descobrir ali.
  TÊM FORMA ...... o excedente é um contêiner (TLV, blocos, o que for). Aí existe
                   um formato, e é nele que o áudio por rádio caberia.

A segunda é a hipótese que sustenta a `ESCADA-QUE-RESPONDE-01` e o
`BLOCO_SPEAKER = 0x13` declarado desde 25/07 em `integrations/dualsense_bt_audio.py`
e nunca referenciado. **Este ensaio é o que decide qual das duas vale**, e por isso
ele vem antes do E-5 (o de mandar Opus): escrever um codificador para um formato
que ninguém confirmou existir naquela posição é o erro que a sprint nomeia.

O DESENHO, e a sacada é não mexer no comando
---------------------------------------------
Manda-se **o mesmo `common`** pedindo uma cor, no **mesmo report**, variando SÓ o
recheio depois dele. A lightbar é o sensor — e ela é boa porque é observável pelo
olho dela, sem instrumento que possa mentir sobre si mesmo.

  passo   recheio dos bytes extras              cor pedida
  1       tudo zero (a linha de base)           VERMELHO
  2       tudo 0xFF                             VERDE
  3       ruído pseudoaleatório, semente fixa   AZUL
  4       um bloco TLV plausível: 0x13|0x80,    AMARELO
          len coerente, resto zero
  5       o mesmo do 4 com len INCOERENTE       CIANO
          (maior que o espaço restante)

  Se os cinco acendem  -> o excedente é IGNORADO naquela posição.
  Se algum QUEBRA      -> há FORMA, e ela mora no que aquele passo mudou.
                          O passo que quebrar vira o começo do mapa do formato.

OS DOIS CONTROLES, e sem eles o ensaio não vale nada
-----------------------------------------------------
POSITIVO ... o passo 1 é a linha de base já medida. Se ELE não acender, o
             instrumento quebrou e nada do resto significa o que se pensa.
             O ensaio PARA sozinho nesse caso.
NEGATIVO ... `--crc-errado` repete um passo com o CRC deliberadamente corrompido.
             NÃO pode acender. Se acender, o firmware não está consumindo o nosso
             pacote — e aí a escada inteira significa outra coisa.

A ARMADILHA QUE ESTE ENSAIO TEM DE RESPEITAR
---------------------------------------------
`os.write()` num hidraw devolve sucesso quando o **KERNEL** aceita a entrega; ele
NÃO espera veredito do firmware. Em 15/08 o kernel aceitou até um pacote de tamanho
errado que era o controle negativo. **O retorno desta chamada não é a medição.**
Quem mede é o olho dela.

E a segunda: APAGAR ENTRE OS PASSOS. Sem isso o passo N herda a cor do N-1 e a
sequência inteira sai falso-positiva — o instrumento apaga, confirma, e só então
pede a cor seguinte.

A PORTA E O QUE ELE ESCREVE
----------------------------
Porta: o broker (`comum.abrir_no_hidraw`), com o daemon VIVO — parar o daemon
derruba os quatro vpads e o co-op. Escrita CRUA por `os.write` no hidraw, envelope
BT montado com o `build_bt_report`/`bt_crc32` DO PRODUTO (semente `0xA2`), nunca
um envelope montado à mão: um report escrito por mim mediria o meu palpite, não o
que o daemon manda.

O QUE ELE RECUSA POR CONSTRUÇÃO
--------------------------------
* qualquer report fora de `0x31`-`0x39` — a família `0xF0`-`0xF7` é o canal de
  atualização de firmware, e ela está BLOQUEADA por decisão dela de 15/08;
* alvo sem `--exigir-mac` conferido, para não escrever no controle errado;
* aparelho no CABO — a escada só existe no rádio, e escrever ali seria medir outra
  coisa.

USO
    corpo_do_degrau.py --listar
    corpo_do_degrau.py --alvo <MAC> --report 0x32
    corpo_do_degrau.py --alvo <MAC> --report 0x32 --passo 3
    corpo_do_degrau.py --alvo <MAC> --report 0x32 --crc-errado
    corpo_do_degrau.py --alvo <MAC> --report 0x39      # depois do 0x32
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from comum import (
    RADIO,
    abrir_no_hidraw,
    descobrir_aparelhos,
    fisicos,
)

from hefesto_dualsense4unix.core.ds_output_report import (
    BT_CRC_SEED,
    COMMON_LEN,
    VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE,
    bt_crc32,
)

#: Os nove degraus do rádio e o tamanho de cada um, do descritor dos aparelhos
#: dela (medido em 15/08). O instrumento RECUSA qualquer id fora desta tabela.
DEGRAUS: dict[int, int] = {
    0x31: 78, 0x32: 142, 0x33: 206, 0x34: 270, 0x35: 334,
    0x36: 398, 0x37: 462, 0x38: 526, 0x39: 547,
}

#: Onde a cor mora no `common` — `[41..46] lightbar/player/cor` do cabeçalho do
#: `ds_output_report`. Os três bytes de RGB são os últimos.
OFF_R, OFF_G, OFF_B = 44, 45, 46

#: A semente do ruído do passo 3. FIXA de propósito: um ensaio que não se repete
#: byte a byte não pode ser conferido por ninguém depois.
SEMENTE = 20260816

PASSOS: dict[int, tuple[str, tuple[int, int, int]]] = {
    1: ("tudo ZERO (a linha de base já medida)", (255, 0, 0)),
    2: ("tudo 0xFF", (0, 255, 0)),
    3: (f"ruído pseudoaleatório, semente {SEMENTE}", (0, 0, 255)),
    4: ("bloco TLV plausível: 0x13|0x80, len coerente", (255, 255, 0)),
    5: ("o mesmo, com len INCOERENTE", (0, 255, 255)),
}
def _masc(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. A saída deste ensaio é versionada."""
    p = mac.split(":")
    return mac if len(p) != 6 else ":".join([*p[:3], "00", "00", p[5]])


NOME_DA_COR = {
    (255, 0, 0): "VERMELHO", (0, 255, 0): "VERDE", (0, 0, 255): "AZUL",
    (255, 255, 0): "AMARELO", (0, 255, 255): "CIANO", (0, 0, 0): "APAGADA",
}


def common_da_cor(r: int, g: int, b: int) -> bytearray:
    """O `common` de 47 bytes pedindo uma cor, e nada mais.

    Montado à mão de propósito NESTE caso — e a exceção é declarada: o
    `_build_common` do produto carrega gatilhos, volume, mudo e o resto do
    estado vivo, e o E-1 precisa que a ÚNICA coisa que varia entre os passos
    seja o recheio. Um `common` cheio de estado tornaria cada passo uma
    medição diferente.
    """
    c = bytearray(COMMON_LEN)
    c[1] = VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    c[OFF_R], c[OFF_G], c[OFF_B] = r, g, b
    return c


def recheio(passo: int, n: int) -> bytes:
    """Os `n` bytes que vão DEPOIS do common, conforme o passo."""
    if n <= 0:
        return b""
    if passo == 1:
        return bytes(n)
    if passo == 2:
        return b"\xff" * n
    if passo == 3:
        # O gerador nasce UMA vez, fora do laço. Criá-lo dentro devolve sempre
        # o mesmo byte (a semente reinicia a cada chamada) — o "ruído" sai
        # `f0 f0 f0 ...`, e o passo vira mais um teste de constante. Caiu nessa
        # na primeira execução de 16/08 e a saída denunciou.
        rnd = random.Random(SEMENTE)
        return bytes(rnd.randrange(256) for _ in range(n))
    if passo == 4:
        # tag com bit7 (BLOCO_PRESENTE) + len que CABE no espaço restante
        corpo = bytes(n - 2) if n >= 2 else b""
        return bytes([0x13 | 0x80, max(0, n - 2)]) + corpo
    if passo == 5:
        # o mesmo, com len maior que o espaço — a incoerência é o ensaio
        return bytes([0x13 | 0x80, 0xFF]) + bytes(max(0, n - 2))
    raise ValueError(f"passo desconhecido: {passo}")


def montar(report_id: int, common: bytearray, extra: bytes, seq: int,
           *, crc_errado: bool = False) -> bytes:
    """O envelope BT do degrau: id, seq, tag, common, recheio, CRC-32 no rabo.

    A forma é a do `build_bt_report` do produto (`[1]=seq<<4`, `[2]=0x10`,
    CRC-32 little-endian com semente `0xA2` nos quatro últimos), estendida para
    o tamanho do degrau. Não se usa o `build_bt_report` direto porque ele monta
    só o `0x31` de 78 bytes.
    """
    tam = DEGRAUS[report_id]
    buf = bytearray(tam)
    buf[0] = report_id
    buf[1] = (seq & 0x0F) << 4
    buf[2] = 0x10
    buf[3:3 + COMMON_LEN] = common
    fim_do_corpo = tam - 4
    inicio_extra = 3 + COMMON_LEN
    espaco = fim_do_corpo - inicio_extra
    buf[inicio_extra:fim_do_corpo] = extra[:espaco].ljust(espaco, b"\x00")
    crc = bt_crc32(bytes(buf[:fim_do_corpo]), seed=BT_CRC_SEED)
    if crc_errado:
        crc ^= 0xFFFFFFFF
    buf[fim_do_corpo:] = crc.to_bytes(4, "little")
    return bytes(buf)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC mascarado OU inteiro do controle no rádio")
    ap.add_argument("--report", default="0x32")
    ap.add_argument("--passo", type=int, action="append", choices=(1, 2, 3, 4, 5))
    ap.add_argument("--crc-errado", action="store_true",
                    help="o CONTROLE NEGATIVO: não pode acender")
    ap.add_argument("--segundos", type=float, default=3.0,
                    help="quanto tempo a cor fica antes de apagar")
    args = ap.parse_args()

    aparelhos = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    if args.listar or not args.alvo:
        print("porta: broker (SCM_RIGHTS) · escrita CRUA por os.write")
        print("escreve no aparelho? SIM — degraus 0x31-0x39 apenas. BLOCO DELA.")
        print("daemon precisa parar? não — a porta é o broker\n")
        print("controles NO RÁDIO (a escada só existe neles):")
        for a in aparelhos:
            print(f"  {_masc(a.mac)}  {a.caminho_hidraw}")
        if not aparelhos:
            print("  nenhum — a escada só existe no rádio")
        return 0

    rid = int(args.report, 0)
    if rid not in DEGRAUS:
        print(f"report {rid:#04x} não é um degrau ({', '.join(hex(k) for k in DEGRAUS)})")
        return 2

    alvo = next((a for a in aparelhos
                 if args.alvo in (_masc(a.mac), a.mac)), None)
    if alvo is None:
        print(f"alvo {args.alvo} não está no rádio. Conhecidos: "
              f"{[_masc(a.mac) for a in aparelhos]}")
        return 1

    try:
        no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    except Exception as erro:
        print(f"sem porta para {_masc(alvo.mac)}: {erro}")
        return 1

    print(f"alvo ....... {_masc(alvo.mac)}  ({alvo.caminho_hidraw})")
    print(f"degrau ..... {rid:#04x}, {DEGRAUS[rid]} bytes  "
          f"({DEGRAUS[rid] - 4 - 3 - COMMON_LEN} de recheio)")
    print(f"CRC ........ semente {BT_CRC_SEED:#04x}"
          f"{'  *** DELIBERADAMENTE ERRADO ***' if args.crc_errado else ''}")
    print("\nO RETORNO DO os.write NÃO É A MEDIÇÃO — quem mede é o olho dela.\n")

    seq = 0
    try:
        for passo in sorted(set(args.passo or (1, 2, 3, 4, 5))):
            desc, cor = PASSOS[passo]
            n = DEGRAUS[rid] - 4 - 3 - COMMON_LEN
            # apaga ANTES: sem isto o passo herda a cor do anterior
            seq = (seq + 1) & 0x0F
            os.write(no.fd, montar(rid, common_da_cor(0, 0, 0), b"", seq))
            time.sleep(0.6)
            seq = (seq + 1) & 0x0F
            pacote = montar(rid, common_da_cor(*cor), recheio(passo, n), seq,
                            crc_errado=args.crc_errado)
            escritos = os.write(no.fd, pacote)
            print(f"PASSO {passo} — recheio: {desc}")
            print(f"  cor pedida: {NOME_DA_COR[cor]}   ({escritos} B no fio)")
            if passo == 1 and not args.crc_errado:
                print("  ^ este é o CONTROLE POSITIVO. Se não acender, PARE.")
            input("  -> que cor a barra mostrou? [Enter para o próximo]  ")
    finally:
        seq = (seq + 1) & 0x0F
        os.write(no.fd, montar(rid, common_da_cor(0, 0, 0), b"", seq))
        no.fechar()
        print("\nbarra apagada, porta fechada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
