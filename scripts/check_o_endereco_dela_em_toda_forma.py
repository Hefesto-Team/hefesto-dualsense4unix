#!/usr/bin/env python3
"""O endereço dela em toda forma — a régua que PERGUNTA AO DONO (local, fora do CI).

O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01 (27/09/2026).

A máscara da casa zera os octetos 4 e 5 e deixa o 1, 2, 3 e 6 à mostra. Os três
portões de anonimato procuram o endereço INTEIRO (por OUI ou por forma), e por
isso não viam os pedaços que entregam o que a máscara esconde:

- o nome de nó `hefesto_som_<6 hex>` / `hefesto_mic_…` / `…HEFESTO<6 hex>`,
  que são os octetos 4, 5 e 6: ao lado do endereço mascarado do mesmo controle,
  devolvem o endereço inteiro. Havia 4 sufixos reais em 16 arquivos
  versionados;
- a fixture de faixa sintética com os octetos de baixo reais
  (`aa:bb:cc:<4>:<5>:<6>`): o `check_endereco_de_radio.py` a lê como exemplo
  didático, e ela carrega exatamente o que a máscara esconde.

Esta régua não adivinha por forma: ela lê os endereços reais DESTA máquina
(`maquina.json` e `controllers.json` do HOME de verdade, `bluetoothctl` e o
sysfs) e procura, na árvore versionada, **toda janela de três octetos que
contenha o octeto 4 ou o 5**. Ela nunca imprime o valor achado: diz o
arquivo, a linha, o endereço pelo índice e o último octeto (que a máscara já
mostra).

AS JANELAS SÃO DO DONO (O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01,
28/09/2026): `core/formas_do_endereco.formas_do_endereco`, nas duas ordens de
byte, com `:` `-` `_` `.`, espaço e colada. Até ali esta régua lia só `[:-]` e
a ordem direta, e o despejo invertido com espaço de um ensaio de 15/08 passava
por ela. E ela procura também os MACs dos virtuais de cada endereço
(`uhid_gamepad.vpad_macs_do_aparelho`, sem copiar a conta nem o número): o
virtual é o endereço disfarçado, e dois bytes do hash ao lado da máscara
bastam para voltar a ele — por isso o virtual com a máscara da casa aplicada
(`02:fe:<3.º>:00:00:<6.º>`, a forma que a máscara do diário de antes de
28/09 escrevia) também é achado, lido com o prefixo.

`--arquivo <caminho>` mede o que se colou FORA da árvore (um «Copiar», um
relato), e `--lar <pasta>` troca a máquina inteira por um lar de mentira: lê
só o `maquina.json` e o `controllers.json` de lá, sem perguntar ao
`bluetoothctl` nem ao sysfs.

Fica fora do CI (`FORA-DO-CI` no `portoes.sh`): no runner não há endereço
nenhum a perguntar.

Isenção de linha, como a do `check_endereco_de_radio.py`:
`<!-- endereco-de-mentira: <motivo> -->`.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if (RAIZ / "src").is_dir() and str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco

EXCLUIR_SUFIXO = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mo", ".woff", ".woff2", ".zip", ".xz", ".gz", ".sha256",
}
ISENCAO = re.compile(r"<!--\s*endereco-de-mentira\s*:\s*\S")

_MAC_COM_SEPARADOR = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})(?![0-9a-f])")
_MAC_COLADO = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{12})(?![0-9a-f])")

#: Os índices (a partir de 0) dos octetos que a máscara esconde.
_ESCONDIDOS = (3, 4)


def _octetos(texto: str) -> tuple[str, ...] | None:
    h = re.sub(r"[:-]", "", texto).lower()
    if len(h) != 12:
        return None
    return tuple(h[i:i + 2] for i in range(0, 12, 2))


def sintetico(o: tuple[str, ...]) -> bool:
    """Endereço que não é de ninguém: o do driver, o didático, o nulo, o broadcast."""
    if o[0] == "02" or o[:2] == ("aa", "bb"):
        return True
    return all(x == "00" for x in o) or all(x == "ff" for x in o)


def enderecos_do_texto(texto: str, *, colado: bool) -> set[tuple[str, ...]]:
    achados: set[tuple[str, ...]] = set()
    padroes = (_MAC_COM_SEPARADOR, _MAC_COLADO) if colado else (_MAC_COM_SEPARADOR,)
    for padrao in padroes:
        for m in padrao.finditer(texto):
            o = _octetos(m.group(1))
            if o is not None and not sintetico(o):
                achados.add(o)
    return achados


def _home_de_verdade() -> Path:
    """O HOME da pessoa, mesmo quando os portões rodam num lar de mentira."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def enderecos_da_maquina(lar: Path | None = None) -> set[tuple[str, ...]]:
    """Os endereços reais desta máquina — ou só os do lar de mentira, quando há um."""
    reais: set[tuple[str, ...]] = set()
    config = (lar or _home_de_verdade()) / ".config" / "hefesto-dualsense4unix"
    for nome in ("maquina.json", "controllers.json"):
        with contextlib.suppress(OSError):
            reais |= enderecos_do_texto((config / nome).read_text(errors="ignore"), colado=True)
    if lar is not None:
        return reais
    for args in (["bluetoothctl", "devices"], ["bluetoothctl", "list"]):
        try:
            saida = subprocess.run(args, capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        reais |= enderecos_do_texto(saida, colado=False)
    for padrao in ("/sys/class/input/*/uniq", "/sys/class/bluetooth/hci*/address"):
        for p in Path("/").glob(padrao.lstrip("/")):
            with contextlib.suppress(OSError):
                reais |= enderecos_do_texto(p.read_text(errors="ignore"), colado=True)
    return reais


def janelas(o: tuple[str, ...]) -> list[tuple[int, tuple[str, str, str]]]:
    """As janelas de três octetos que contêm um octeto escondido não nulo."""
    saida = []
    for inicio in range(1, 4):
        fim = inicio + 3
        escondidos = [i for i in _ESCONDIDOS if inicio <= i < fim]
        if any(o[i] != "00" for i in escondidos):
            saida.append((inicio, (o[inicio], o[inicio + 1], o[inicio + 2])))
    return saida


#: Uma sequência hex solta, de 6 a 12 dígitos: o nome de nó (6), o endereço
#: colado (12) e tudo entre. Mais longa que 12 é hash, e não endereço.
_SEQUENCIA_HEX = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{6,12}(?![0-9a-f])")


def _separadas(o: tuple[str, ...]) -> list[str]:
    """Os pedaços COM separador que o dono diz entregarem o 4.º ou o 5.º octeto."""
    return sorted(p for p in formas_do_endereco(o) if p == p.lower() and len(p) == 8)


def _coladas(o: tuple[str, ...]) -> list[str]:
    return sorted(p for p in formas_do_endereco(o) if p == p.lower() and len(p) == 6)


def padrao_das_janelas(reais: set[tuple[str, ...]]) -> dict[str, re.Pattern[str]]:
    """Rótulo (`E<n>…<último octeto>`) → regex das janelas COM separador, pelo dono."""
    padroes: dict[str, re.Pattern[str]] = {}
    for n, o in enumerate(sorted(reais)):
        alternativas = [re.escape(p) for p in _separadas(o)]
        if alternativas:
            padroes[f"E{n}…{o[5]}"] = re.compile(
                r"(?i)(?<![0-9a-f])(?:" + "|".join(alternativas) + r")(?![0-9a-f])"
            )
    return padroes


def janelas_coladas(reais: set[tuple[str, ...]]) -> dict[str, str]:
    """As janelas SEM separador (`aabbcc`, nas duas ordens) → o rótulo do endereço."""
    return {
        pedaco: f"E{n}…{o[5]}"
        for n, o in enumerate(sorted(reais))
        for pedaco in _coladas(o)
    }


def virtuais_da_maquina(reais: set[tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Rótulo (`V<k> de E<n>`) → os octetos de cada MAC de virtual de cada endereço.

    Todos os que o dono dos vivos pode vestir, até o fim da lista dele: o
    número de MACs por aparelho é do `uhid_gamepad`, e uma cópia dele aqui
    envelheceria calada. O jogador não entra na conta de quem tem endereço.

    O rótulo não leva octeto nenhum do virtual: todos os quatro de baixo são
    hash do endereço.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_macs_do_aparelho

    virtuais: dict[str, tuple[str, ...]] = {}
    for n, o in enumerate(sorted(reais)):
        for k, mac in enumerate(vpad_macs_do_aparelho(":".join(o), 1)):
            virtuais[f"V{k} de E{n}"] = tuple(mac.lower().split(":"))
    return virtuais


#: Os separadores do dono, e o colado.
_SEPARADORES = (":", "-", "_", ".", " ", "")


def pedacos_dos_virtuais(virtuais: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Os QUATRO bytes do hash de cada virtual, nas duas ordens e em toda grafia → o rótulo.

    Quatro, e não a janela de três do dono, por medida (28/09/2026): a árvore
    tem 153 mil janelas de três octetos separados por espaço (quase todas no
    despejo decodificado do HCI de 15/08), e 64 virtuais por endereço fariam
    dezenas de janelas casarem por acaso — o portão ficaria vermelho de ruído.
    Os quatro bytes juntos são o virtual inteiro menos o prefixo, e o acaso
    deles é desprezível.

    E O VIRTUAL COM A MÁSCARA DA CASA (28/09/2026, conferência): zerar o 4.º e
    o 5.º octetos do virtual deixa o 3.º e o 6.º, dois bytes do hash, e com a
    máscara do endereço ao lado sobram uns dois candidatos (a medida da
    sprint). Esses dois bytes sozinhos casariam por acaso com o ruído acima,
    então eles se leem com o prefixo, os seis octetos juntos
    (`02:fe:<3.º>:00:00:<6.º>`, nas duas ordens e em toda grafia): com o
    prefixo, o acaso volta a ser desprezível.
    """
    pedacos: dict[str, str] = {}
    for rotulo, o in virtuais.items():
        com_a_mascara = (*o[:3], "00", "00", o[5])
        for ordem in (o[2:], o[2:][::-1], com_a_mascara, com_a_mascara[::-1]):
            for separador in _SEPARADORES:
                pedacos[separador.join(ordem)] = rotulo
    return pedacos


#: Uma corrida de três octetos ou mais com o MESMO separador, ou colada.
_CORRIDA = re.compile(
    r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}([:\-_. ])[0-9a-f]{2}(?:\1[0-9a-f]{2})+|[0-9a-f]{8,})"
    r"(?![0-9a-f])"
)


def achados_dos_virtuais(linha: str, pedacos: dict[str, str]) -> list[str]:
    """Os rótulos dos virtuais cujos quatro bytes de hash (ou os seis octetos
    com a máscara da casa) estão na linha.

    Por dicionário, e não por regex: são 64 virtuais por endereço, e uma regex
    por rótulo custaria 64 varreduras de cada linha da árvore. A corrida colada
    se lê como a do dono: a par, alinhada pelo começo; a ímpar não diz onde
    começa o octeto, e as duas paridades são lidas.
    """
    if not pedacos:
        return []
    rotulos = []
    for m in _CORRIDA.finditer(linha):
        separador = m.group(1) or ""
        corrida = m.group(0).lower()
        leituras = ([corrida.split(separador)] if separador else [
            [corrida[i:i + 2] for i in range(paridade, len(corrida) - 1, 2)]
            for paridade in ((0, 1) if len(corrida) % 2 else (0,))
        ])
        for octetos in leituras:
            for largura in (4, 6):
                for i in range(len(octetos) - largura + 1):
                    rotulo = pedacos.get(separador.join(octetos[i:i + largura]))
                    if rotulo:
                        rotulos.append(rotulo)
    return rotulos


def achados_colados(linha: str, coladas: dict[str, str]) -> list[str]:
    """Os rótulos das janelas coladas, alinhadas a octeto, em cada sequência hex.

    Olha DENTRO da sequência: o endereço colado inteiro (`aabbccddeeff`) tem a
    janela dos octetos 4 a 6 a partir do sétimo dígito, e ela não tem borda.
    """
    rotulos = []
    for m in _SEQUENCIA_HEX.finditer(linha):
        seq = m.group(0).lower()
        if len(seq) % 2:
            continue
        for inicio in range(0, len(seq) - 4, 2):
            rotulo = coladas.get(seq[inicio:inicio + 6])
            if rotulo:
                rotulos.append(rotulo)
    return rotulos


def arquivos_versionados() -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=RAIZ, check=True, capture_output=True, text=True,
    ).stdout
    return [
        RAIZ / nome
        for nome in saida.split("\0")
        if nome and (RAIZ / nome).suffix.lower() not in EXCLUIR_SUFIXO
    ]


#: O que uma linha tem de ter para carregar um pedaço: três octetos separados
#: ou seis hex colados. Sem isto, nenhum pedaço cabe nela, e as regex por
#: endereço nem rodam — medido em 28/09/2026, elas eram 44 dos 55 segundos
#: da varredura com dez endereços, quase todos gastos em linha de prosa.
_PODE_TER_PEDACO = re.compile(
    r"(?i)[0-9a-f]{2}[:\-_. ][0-9a-f]{2}[:\-_. ][0-9a-f]{2}|[0-9a-f]{6}"
)


def _nome(p: Path) -> str:
    """O caminho relativo à árvore, ou o de fora como veio (o `--arquivo`)."""
    try:
        return str(p.resolve().relative_to(RAIZ))
    except ValueError:
        return str(p)


def varrer(
    arquivos: list[Path],
    padroes: dict[str, re.Pattern[str]],
    coladas: dict[str, str] | None = None,
    virtuais: dict[str, str] | None = None,
) -> list[str]:
    achados = []
    for p in arquivos:
        try:
            texto = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            if not _PODE_TER_PEDACO.search(linha) or ISENCAO.search(linha):
                continue
            rotulos = [r for r, padrao in padroes.items() for _ in padrao.findall(linha)]
            rotulos += achados_dos_virtuais(linha, virtuais or {})
            rotulos += achados_colados(linha, coladas or {})
            for rotulo in sorted(set(rotulos)):
                k = rotulos.count(rotulo)
                achados.append(f"{_nome(p)}:{n}: {k}x o endereço {rotulo}")
    return achados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arquivo", action="append", type=Path, default=[],
                        help="mede este arquivo (fora da árvore) em vez do versionado")
    parser.add_argument("--lar", type=Path, default=None,
                        help="um lar de mentira: os endereços saem só do config dele")
    args = parser.parse_args(argv)
    reais = enderecos_da_maquina(args.lar)
    if not reais:
        print("NÃO MEDIDO: esta máquina não tem endereço real a perguntar.")
        return 0
    achados = varrer(
        args.arquivo or arquivos_versionados(),
        padrao_das_janelas(reais),
        janelas_coladas(reais),
        pedacos_dos_virtuais(virtuais_da_maquina(reais)),
    )
    if achados:
        print(f"FALHA: {len(achados)} linha(s) com os octetos 4 ou 5 de um endereço dela.\n")
        for a in achados[:60]:
            print("  " + a)
        if len(achados) > 60:
            print(f"  … e mais {len(achados) - 60}.")
        print("\nA máscara da casa zera os octetos 4 e 5 em TODA forma:")
        print("  AA:BB:CC:DD:EE:FF -> AA:BB:CC:00:00:FF   e   hefesto_som_DDEEFF -> hefesto_som_0000FF")
        print("  e o virtual derivado sai 02:fe:80:00:00:00 (core/formas_do_endereco).")
        return 1
    onde = "nos arquivos pedidos" if args.arquivo else "na árvore"
    print(f"OK: {len(reais)} endereço(s) da máquina e os virtuais deles, "
          f"nenhum pedaço escondido {onde}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
