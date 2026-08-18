#!/usr/bin/env python3
"""Mascara o MAC de hardware REAL dentro de uma captura `.btsnoop` BINÁRIA.

POR QUE ESTE ARQUIVO EXISTE (15/08/2026). **GRAU: MEDIDO.**
---------------------------------------------------------

A dona decidiu versionar o lastro do estudo PAREADO inteiro, **binário
incluído**. Só que o `.btsnoop` do `btmon` carrega o endereço do adaptador
Bluetooth do host em BINÁRIO e em **ordem de byte invertida** (little-endian) —
é assim que o HCI escreve `BD_ADDR` no fio. Um endereço `d8:44:89:xx:xx:xx`
aparece no arquivo como os seis bytes `xx xx xx 89 44 d8`, de trás para a
frente, e **nenhum portão de texto desta casa o vê**: não há dois-pontos, não há
hexadecimal escrito, não há sequer uma linha.

Medido na captura de 15/08 (`btmon.btsnoop`, 238451 B, 2153 registros): **duas**
ocorrências do endereço do adaptador, ambas em little-endian, aos deslocamentos
170 e 232. Em big-endian: **zero**. Uma varredura feita numa ordem de byte só —
a "natural", a que se lê no `btmon` — teria devolvido nada e o arquivo teria
entrado no repositório público carregando o endereço.

**A régua, então, é esta: procure nas DUAS ordens, e prove que procurou.** O
modo ``--conferir`` imprime a contagem das duas, mesmo quando uma delas é zero,
justamente para que o zero seja um resultado declarado e não um esquecimento.

O QUE ELE FAZ, E O QUE ELE SE RECUSA A FAZER
--------------------------------------------

- Máscara da casa, a mesma dos documentos: **octetos 4 e 5 zerados**. O OUI
  (que é público) e o último octeto ficam — é o que permite continuar
  distinguindo dois aparelhos numa mesma captura sem identificar nenhum.
- **Tamanho preservado, byte a byte.** Só dois bytes por ocorrência mudam de
  valor; nada é inserido nem removido. Se a saída mudar de tamanho, o script
  **não escreve** e sai com erro — um `.btsnoop` de tamanho diferente é um
  `.btsnoop` com o índice de registros deslocado, ou seja, uma captura
  falsificada.
- **Só mexe em PAYLOAD.** O formato é lido de verdade: 16 bytes de cabeçalho,
  depois registros de 24 bytes de cabeçalho + N bytes de dados. Se uma
  ocorrência cair dentro de um cabeçalho de registro (onde ela seria, quase
  certamente, coincidência de bytes de comprimento/carimbo de tempo), o script
  **recusa** o arquivo inteiro em vez de zerar dois bytes de estrutura.

A LISTA DE OUIs É ESPELHO, E HÁ TESTE CONTRA A DIVERGÊNCIA
-----------------------------------------------------------

A lista canônica mora no portão, ``tests/unit/test_docs_mac_anonimato.py``
(``_OUIS_REAIS_OCTETOS``). Aqui há uma cópia, porque um script de ``scripts/``
não importa de ``tests/`` — e ``tests/unit/test_mascarar_btsnoop.py`` compara as
duas tupla a tupla. Duas cópias que podem divergir em silêncio seriam a mesma
classe de defeito do BURACO-DO-PORTÃO-01: controle novo entra na bancada, o OUI
entra num lugar só, e o outro lugar segue cego.

USO
---

    scripts/mascarar_btsnoop.py --conferir captura.btsnoop
    scripts/mascarar_btsnoop.py captura.btsnoop -o captura-mascarada.btsnoop
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

#: ESPELHO de ``tests/unit/test_docs_mac_anonimato.py::_OUIS_REAIS_OCTETOS``.
#: Ver o parágrafo "A LISTA DE OUIs É ESPELHO" no topo: há teste que reprova a
#: divergência. Controle novo na bancada = OUI novo NOS DOIS, no mesmo commit.
_OUIS_REAIS_OCTETOS = (
    ("d8", "44", "89"),
    ("a0", "fa", "9c"),
    ("e4", "17", "d8"),
    ("e0", "f6", "b5"),
    ("48", "b2", "5d"),
    ("14", "3a", "9a"),
    ("d4", "2f", "4b"),
    ("44", "46", "48"),
)

#: O cabeçalho do formato: 8 bytes de identificação + versão + tipo de enlace.
ASSINATURA_BTSNOOP = b"btsnoop\x00"
TAMANHO_CABECALHO = 16
#: Cabeçalho de cada registro: 4 campos de 32 bits + carimbo de tempo de 64.
TAMANHO_CABECALHO_REGISTRO = 24

#: Um endereço Bluetooth tem 6 octetos.
TAMANHO_MAC = 6

ORDEM_BE = "big-endian"
ORDEM_LE = "little-endian"


@dataclass(frozen=True)
class Ocorrencia:
    """Um endereço de hardware real achado dentro de bytes.

    ``inicio`` é o deslocamento do PRIMEIRO byte do campo de 6 octetos, na
    ordem em que ele está gravado no arquivo — não a do OUI.
    """

    inicio: int
    ordem: str
    oui: str
    mac: str
    mascarado: bool

    def __str__(self) -> str:
        estado = "já mascarado" if self.mascarado else "CRU"
        return f"offset {self.inicio} ({self.ordem}): {self.mac} — {estado}"


def _oui_bytes(octetos: tuple[str, str, str]) -> bytes:
    return bytes(int(o, 16) for o in octetos)


def ocorrencias(dados: bytes) -> list[Ocorrencia]:
    """Acha todo MAC de OUI real em ``dados``, nas DUAS ordens de byte.

    Devolve a lista ordenada por deslocamento, com ``mascarado`` dizendo se
    aquela ocorrência já está na máscara da casa (octetos 4 e 5 zerados).
    """
    achados: list[Ocorrencia] = []
    for octetos in _OUIS_REAIS_OCTETOS:
        oui_be = _oui_bytes(octetos)
        oui_le = oui_be[::-1]
        rotulo = ":".join(octetos)

        # BIG-ENDIAN: o OUI abre o campo. Octetos 4 e 5 vêm logo depois.
        pos = dados.find(oui_be)
        while pos != -1:
            if pos + TAMANHO_MAC <= len(dados):
                campo = dados[pos : pos + TAMANHO_MAC]
                achados.append(
                    Ocorrencia(
                        inicio=pos,
                        ordem=ORDEM_BE,
                        oui=rotulo,
                        mac=campo.hex(":"),
                        mascarado=campo[3] == 0 and campo[4] == 0,
                    )
                )
            pos = dados.find(oui_be, pos + 1)

        # LITTLE-ENDIAN: o campo está de trás para a frente, então o OUI
        # FECHA os 6 bytes e os octetos 4 e 5 são os dois anteriores a ele.
        pos = dados.find(oui_le)
        while pos != -1:
            inicio = pos - (TAMANHO_MAC - len(oui_le))
            if inicio >= 0:
                campo = dados[inicio : inicio + TAMANHO_MAC]
                achados.append(
                    Ocorrencia(
                        inicio=inicio,
                        ordem=ORDEM_LE,
                        oui=rotulo,
                        # Impresso na ordem HUMANA, que é a inversa da gravada.
                        mac=campo[::-1].hex(":"),
                        mascarado=campo[1] == 0 and campo[2] == 0,
                    )
                )
            pos = dados.find(oui_le, pos + 1)

    return sorted(achados, key=lambda o: (o.inicio, o.ordem))


def cruas(dados: bytes) -> list[Ocorrencia]:
    """Só as ocorrências que ainda NÃO estão mascaradas — as que vazam."""
    return [o for o in ocorrencias(dados) if not o.mascarado]


class BtsnoopInvalidoError(ValueError):
    """O arquivo não é um `.btsnoop` que este script saiba tratar."""


def faixas_de_payload(dados: bytes) -> list[tuple[int, int]]:
    """Percorre o formato e devolve as faixas ``[inicio, fim)`` de dados.

    Levanta ``BtsnoopInvalidoError`` se a assinatura não bater ou se um registro
    prometer mais bytes do que o arquivo tem — recusar é melhor do que mascarar
    às cegas um arquivo que não é o que diz ser.
    """
    if not dados.startswith(ASSINATURA_BTSNOOP):
        raise BtsnoopInvalidoError(
            "assinatura ausente: os 8 primeiros bytes não são `btsnoop\\0`"
        )
    if len(dados) < TAMANHO_CABECALHO:
        raise BtsnoopInvalidoError(
            f"arquivo com {len(dados)} B: menor que o cabeçalho de "
            f"{TAMANHO_CABECALHO} B"
        )

    faixas: list[tuple[int, int]] = []
    pos = TAMANHO_CABECALHO
    while pos < len(dados):
        fim_do_cabecalho = pos + TAMANHO_CABECALHO_REGISTRO
        if fim_do_cabecalho > len(dados):
            raise BtsnoopInvalidoError(
                f"registro truncado no offset {pos}: faltam bytes de cabeçalho"
            )
        incluidos = int.from_bytes(dados[pos + 4 : pos + 8], "big")
        fim_do_payload = fim_do_cabecalho + incluidos
        if fim_do_payload > len(dados):
            raise BtsnoopInvalidoError(
                f"registro no offset {pos} promete {incluidos} B de dados e o "
                f"arquivo acaba antes"
            )
        faixas.append((fim_do_cabecalho, fim_do_payload))
        pos = fim_do_payload
    return faixas


def _dentro_de_payload(faixas: list[tuple[int, int]], inicio: int, fim: int) -> bool:
    return any(a <= inicio and fim <= b for a, b in faixas)


def mascarar(dados: bytes) -> tuple[bytes, list[Ocorrencia]]:
    """Devolve ``(bytes mascarados, ocorrências que estavam cruas)``.

    Recusa (``BtsnoopInvalidoError``) se alguma ocorrência crua cair fora de um
    payload: zerar dois bytes de um cabeçalho de registro corromperia o índice
    da captura, e uma captura corrompida não é evidência.
    """
    faixas = faixas_de_payload(dados)
    achados = cruas(dados)
    fora = [
        o
        for o in achados
        if not _dentro_de_payload(faixas, o.inicio, o.inicio + TAMANHO_MAC)
    ]
    if fora:
        raise BtsnoopInvalidoError(
            "ocorrência fora de payload — recuso mascarar estrutura do "
            "formato:\n  " + "\n  ".join(str(o) for o in fora)
        )

    saida = bytearray(dados)
    for o in achados:
        if o.ordem == ORDEM_BE:
            # d8 44 89 [4] [5] [6] -> zera os dois do meio.
            saida[o.inicio + 3] = 0
            saida[o.inicio + 4] = 0
        else:
            # [6] [5] [4] 89 44 d8 -> os mesmos dois octetos, na ordem gravada.
            saida[o.inicio + 1] = 0
            saida[o.inicio + 2] = 0

    if len(saida) != len(dados):
        # Inalcançável por construção (só há atribuição em índice existente), e
        # é exatamente por isso que a checagem fica: o dia em que alguém trocar
        # a substituição por um `replace`, o script para em vez de escrever uma
        # captura de tamanho errado.
        raise BtsnoopInvalidoError(
            f"a saída teria {len(saida)} B contra {len(dados)} B da entrada — "
            "recuso escrever: `.btsnoop` de tamanho diferente é captura "
            "falsificada"
        )
    return bytes(saida), achados


def _relatorio(caminho: Path, dados: bytes) -> int:
    todas = ocorrencias(dados)
    por_ordem = {
        ORDEM_BE: [o for o in todas if o.ordem == ORDEM_BE],
        ORDEM_LE: [o for o in todas if o.ordem == ORDEM_LE],
    }
    print(f"{caminho}: {len(dados)} B")
    # As DUAS ordens saem impressas mesmo quando uma delas é zero: o zero é
    # resultado declarado, não busca esquecida.
    for ordem in (ORDEM_BE, ORDEM_LE):
        achados = por_ordem[ordem]
        crus = [o for o in achados if not o.mascarado]
        print(f"  {ordem:<13} {len(achados)} ocorrência(s), {len(crus)} crua(s)")
        for o in achados:
            print(f"    {o}")
    return len([o for o in todas if not o.mascarado])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mascara (octetos 4 e 5 zerados) o MAC real dentro de um .btsnoop, "
            "procurando nas duas ordens de byte e preservando o tamanho."
        )
    )
    parser.add_argument("entrada", type=Path, help="captura .btsnoop de origem")
    parser.add_argument(
        "-o",
        "--saida",
        type=Path,
        help="arquivo a escrever (obrigatório fora de --conferir)",
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="só relata as ocorrências nas duas ordens; não escreve nada. "
        "Sai 1 se sobrar alguma crua.",
    )
    args = parser.parse_args(argv)

    try:
        dados = args.entrada.read_bytes()
    except OSError as erro:
        print(f"não consegui ler {args.entrada}: {erro}", file=sys.stderr)
        return 2

    if args.conferir:
        return 1 if _relatorio(args.entrada, dados) else 0

    if args.saida is None:
        parser.error("faltou -o/--saida (ou use --conferir)")

    try:
        saida, achados = mascarar(dados)
    except BtsnoopInvalidoError as erro:
        print(f"{args.entrada}: {erro}", file=sys.stderr)
        return 2

    args.saida.write_bytes(saida)
    conferencia = args.saida.read_bytes()
    if len(conferencia) != len(dados):
        print(
            f"{args.saida}: escrevi {len(conferencia)} B contra {len(dados)} B "
            "da entrada — o arquivo está errado",
            file=sys.stderr,
        )
        return 2
    if cruas(conferencia):
        print(f"{args.saida}: ainda há MAC cru depois de mascarar", file=sys.stderr)
        return 2

    print(
        f"{args.saida}: {len(achados)} ocorrência(s) mascarada(s), "
        f"{len(conferencia)} B (mesmo tamanho da entrada)"
    )
    for o in achados:
        print(f"  {o}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
