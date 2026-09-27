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
contenha o octeto 4 ou o 5**, com dois-pontos, com hífen e colada. Ela nunca
imprime o valor achado: diz o arquivo, a linha, o endereço pelo índice e o
último octeto (que a máscara já mostra).

Fica fora do CI (`FORA-DO-CI` no `portoes.sh`): no runner não há endereço
nenhum a perguntar.

Isenção de linha, como a do `check_endereco_de_radio.py`:
`<!-- endereco-de-mentira: <motivo> -->`.
"""
from __future__ import annotations

import contextlib
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

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


def enderecos_da_maquina() -> set[tuple[str, ...]]:
    reais: set[tuple[str, ...]] = set()
    config = _home_de_verdade() / ".config" / "hefesto-dualsense4unix"
    for nome in ("maquina.json", "controllers.json"):
        with contextlib.suppress(OSError):
            reais |= enderecos_do_texto((config / nome).read_text(errors="ignore"), colado=True)
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


def padrao_das_janelas(reais: set[tuple[str, ...]]) -> dict[str, re.Pattern[str]]:
    """Rótulo (`E<n>…<último octeto>`) → regex das janelas COM separador."""
    padroes: dict[str, re.Pattern[str]] = {}
    for n, o in enumerate(sorted(reais)):
        alternativas = [f"{a}[:-]{b}[:-]{c}" for _inicio, (a, b, c) in janelas(o)]
        if alternativas:
            padroes[f"E{n}…{o[5]}"] = re.compile(
                r"(?i)(?<![0-9a-f])(?:" + "|".join(alternativas) + r")(?![0-9a-f])"
            )
    return padroes


def janelas_coladas(reais: set[tuple[str, ...]]) -> dict[str, str]:
    """As janelas SEM separador (`aabbcc`) → o rótulo do endereço."""
    return {
        f"{a}{b}{c}": f"E{n}…{o[5]}"
        for n, o in enumerate(sorted(reais))
        for _inicio, (a, b, c) in janelas(o)
    }


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


def varrer(
    arquivos: list[Path],
    padroes: dict[str, re.Pattern[str]],
    coladas: dict[str, str] | None = None,
) -> list[str]:
    achados = []
    for p in arquivos:
        try:
            texto = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(texto.splitlines(), 1):
            if ISENCAO.search(linha):
                continue
            rotulos = [r for r, padrao in padroes.items() for _ in padrao.findall(linha)]
            rotulos += achados_colados(linha, coladas or {})
            for rotulo in sorted(set(rotulos)):
                k = rotulos.count(rotulo)
                achados.append(f"{p.relative_to(RAIZ)}:{n}: {k}x o endereço {rotulo}")
    return achados


def main() -> int:
    reais = enderecos_da_maquina()
    if not reais:
        print("NÃO MEDIDO: esta máquina não tem endereço real a perguntar.")
        return 0
    achados = varrer(arquivos_versionados(), padrao_das_janelas(reais), janelas_coladas(reais))
    if achados:
        print(f"FALHA: {len(achados)} linha(s) com os octetos 4 ou 5 de um endereço dela.\n")
        for a in achados[:60]:
            print("  " + a)
        if len(achados) > 60:
            print(f"  … e mais {len(achados) - 60}.")
        print("\nA máscara da casa zera os octetos 4 e 5 em TODA forma:")
        print("  AA:BB:CC:DD:EE:FF -> AA:BB:CC:00:00:FF   e   hefesto_som_DDEEFF -> hefesto_som_0000FF")
        return 1
    print(f"OK: {len(reais)} endereço(s) da máquina, nenhum pedaço escondido na árvore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
