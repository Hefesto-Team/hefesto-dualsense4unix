#!/usr/bin/env python3
"""O endereço dela em toda forma — a régua que PERGUNTA AO DONO (local, fora do CI)."""
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

from hefesto_dualsense4unix.core.formas_do_endereco import _UUID, formas_do_endereco

EXCLUIR_SUFIXO = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mo", ".woff", ".woff2", ".zip", ".xz", ".gz", ".sha256",
}
ISENCAO = re.compile(r"<!--\s*endereco-de-mentira\s*:\s*\S")

_MAC_COM_SEPARADOR = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})(?![0-9a-f])")
_MAC_COLADO = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{12})(?![0-9a-f])")

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
    """Os endereços de uma FONTE da máquina (o config, o ``bluetoothctl``, o sysfs)."""
    texto = _UUID.sub(" ", texto)
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
    """Rótulo (`V<k> de E<n>`) → os octetos de cada MAC de virtual de cada endereço."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_macs_do_aparelho

    virtuais: dict[str, tuple[str, ...]] = {}
    for n, o in enumerate(sorted(reais)):
        for k, mac in enumerate(vpad_macs_do_aparelho(":".join(o), 1)):
            virtuais[f"V{k} de E{n}"] = tuple(mac.lower().split(":"))
    return virtuais


_SEPARADORES = (":", "-", "_", ".", " ", "")


def pedacos_dos_virtuais(virtuais: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Os QUATRO bytes do hash de cada virtual, nas duas ordens e em toda grafia → o rótulo."""
    pedacos: dict[str, str] = {}
    for rotulo, o in virtuais.items():
        com_a_mascara = (*o[:3], "00", "00", o[5])
        for ordem in (o[2:], o[2:][::-1], com_a_mascara, com_a_mascara[::-1]):
            for separador in _SEPARADORES:
                pedacos[separador.join(ordem)] = rotulo
    return pedacos


_CORRIDA = re.compile(
    r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}([:\-_. ])[0-9a-f]{2}(?:\1[0-9a-f]{2})+|[0-9a-f]{8,})"
    r"(?![0-9a-f])"
)


def achados_dos_virtuais(linha: str, pedacos: dict[str, str]) -> list[str]:
    """Os rótulos dos virtuais cujos quatro bytes de hash (ou os seis octetos"""
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
    """Os rótulos das janelas coladas, alinhadas a octeto, em cada sequência hex."""
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
