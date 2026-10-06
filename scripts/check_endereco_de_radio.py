#!/usr/bin/env python3
"""check_endereco_de_radio.py — nenhum endereço de rádio REAL em arquivo versionado."""
from __future__ import annotations

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
    ".mo", ".woff", ".woff2", ".zip", ".xz", ".sha256",
}
EXCLUIR_CAMINHO = {
    "docs/usage/assets/PROVA-DA-FOTO.txt",
    "scripts/check_endereco_de_radio.py",
    "scripts/check_o_endereco_em_toda_forma.py",
    "poetry.lock", "package-lock.json", "flake.lock",
}

MAC = re.compile(r"\b([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):"
                 r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\b")

ISENCAO = re.compile(r"<!--\s*endereco-de-mentira\s*:\s*\S")
SERIAL = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])")

CONSTANTES_DE_ESPECIFICACAO = {
    "00805F9B34FB",
    # interface que a RE Engine enumera para achar a háptica do DualSense
    "00A0C9223196",
}


def mascarado(o4: str, o5: str) -> bool:
    """A máscara da casa: octetos 4 e 5 zerados."""
    return o4 == "00" and o5 == "00"


def sintetico(octetos: list[str]) -> bool:
    """Endereço que não identifica ninguém: fabricado, didático ou reservado."""
    o1, o2 = octetos[0], octetos[1]
    if o1 == "02":
        return True
    if (o1, o2) == ("AA", "BB"):
        return True
    if all(o == "FF" for o in octetos):
        return True
    return all(o == "00" for o in octetos)


def acusa_mac(linha: str) -> list[str]:
    achados = []
    for m in MAC.finditer(linha):
        o = [g.upper() for g in m.groups()]
        if mascarado(o[3], o[4]) or sintetico(o):
            continue
        achados.append(m.group(0))
    return achados


def acusa_serial(linha: str) -> list[str]:
    achados = []
    for m in SERIAL.finditer(linha):
        s = m.group(1).upper()
        if s[6:10] == "0000":
            continue
        if not re.search(r"[A-F]", s):
            continue
        if m.group(1) != s:
            continue
        if s[:2] == "02":
            continue
        if s[:4] == "AABB":
            continue
        if s in CONSTANTES_DE_ESPECIFICACAO:
            continue
        achados.append(m.group(1))
    return achados


NO_DE_SOM = re.compile(
    r"(?:hefesto_(?:som|mic|haptica|hapt|dualsense_bt)_|HEFESTO)([0-9A-Fa-f]{6})(?![0-9A-Fa-f])"
)


def acusa_no(linha: str) -> list[str]:
    """Nomes de nó de som cujo sufixo não está mascarado (`0000` e o octeto 6)."""
    return [m.group(0) for m in NO_DE_SOM.finditer(linha) if m.group(1)[:4] != "0000"]


_CORRIDA = re.compile(
    r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}([:\-_. ])[0-9a-f]{2}(?:\1[0-9a-f]{2})+|[0-9a-f]{6,})"
    r"(?![0-9a-f])"
)


def octetos_de(achado: str) -> tuple[str, ...] | None:
    """Os seis octetos (minúsculos) de um endereço acusado, em qualquer grafia."""
    hexa = re.sub(r"[^0-9A-Fa-f]", "", achado).lower()
    return tuple(hexa[i:i + 2] for i in range(0, 12, 2)) if len(hexa) == 12 else None


def pedacos_dos_acusados(acusados: list[tuple[str, ...]]) -> dict[str, str]:
    """As janelas de cada endereço acusado, pelo dono → o rótulo (`A<n>`), sem valor."""
    pedacos: dict[str, str] = {}
    for n, octetos in enumerate(acusados):
        for pedaco in formas_do_endereco(octetos):
            pedacos.setdefault(pedaco.lower(), f"A{n}")
    return pedacos


def acusa_pedaco(linha: str, pedacos: dict[str, str]) -> list[str]:
    """Os rótulos dos acusados que têm uma janela nesta linha."""
    rotulos = []
    for m in _CORRIDA.finditer(linha):
        separador = m.group(1) or ""
        corrida = m.group(0).lower()
        for octetos in _leituras_da_corrida(corrida, separador):
            for i in range(len(octetos) - 2):
                rotulo = pedacos.get(separador.join(octetos[i:i + 3]))
                if rotulo:
                    rotulos.append(rotulo)
    return rotulos


def _leituras_da_corrida(corrida: str, separador: str) -> list[list[str]]:
    """Os octetos da corrida: um jeito com separador, e um ou dois colada."""
    if separador:
        return [corrida.split(separador)]
    return [[corrida[i:i + 2] for i in range(paridade, len(corrida) - 1, 2)]
            for paridade in ((0, 1) if len(corrida) % 2 else (0,))]


def arquivos_versionados() -> list[Path]:
    try:
        saida = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            cwd=RAIZ, check=True,
            capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(p for p in RAIZ.rglob("*") if p.is_file())
    fora = []
    for nome in saida.split("\0"):
        if not nome:
            continue
        if nome in EXCLUIR_CAMINHO:
            continue
        p = RAIZ / nome
        if p.suffix.lower() in EXCLUIR_SUFIXO:
            continue
        fora.append(p)
    return fora


def _texto_de(p: Path) -> str | None:
    """O texto do arquivo — e o de DENTRO dele, quando é comprimido."""
    if p.suffix.lower() == ".gz":
        import gzip
        try:
            return gzip.decompress(p.read_bytes()).decode("utf-8", errors="strict")
        except (OSError, EOFError, UnicodeDecodeError, gzip.BadGzipFile):
            return None
    return p.read_text(encoding="utf-8", errors="strict")


def main() -> int:
    achados: list[str] = []
    acusados: list[tuple[str, ...]] = []
    lidos: list[Path] = []
    for p in arquivos_versionados():
        try:
            texto = _texto_de(p)
        except (UnicodeDecodeError, OSError):
            continue
        if texto is None:
            continue
        rel = p.relative_to(RAIZ)
        lidos.append(p)
        for n, linha in enumerate(texto.splitlines(), 1):
            if ISENCAO.search(linha):
                continue
            for a in acusa_mac(linha):
                achados.append(f"{rel}:{n}: MAC real    {a}")
                acusados.append(octetos_de(a) or ())
            for a in acusa_serial(linha):
                achados.append(f"{rel}:{n}: serial USB  {a}")
                acusados.append(octetos_de(a) or ())
            if not str(rel).startswith("tests/"):
                for a in acusa_no(linha):
                    achados.append(f"{rel}:{n}: nó de som   {a}")

    pedacos = pedacos_dos_acusados([o for o in dict.fromkeys(acusados) if o])
    ja = {a.split(": ", 1)[0] for a in achados}
    for p in lidos if pedacos else ():
        rel = p.relative_to(RAIZ)
        for n, linha in enumerate((_texto_de(p) or "").splitlines(), 1):
            if f"{rel}:{n}" in ja or ISENCAO.search(linha):
                continue
            for rotulo in sorted(set(acusa_pedaco(linha, pedacos))):
                achados.append(f"{rel}:{n}: pedaço do endereço acusado {rotulo}")

    if achados:
        print(f"FALHA: {len(achados)} endereço(s) de rádio REAL em arquivo versionado.\n")
        for a in achados[:40]:
            print("  " + a)
        if len(achados) > 40:
            print(f"  … e mais {len(achados) - 40}.")
        print("\nA máscara da casa zera os octetos 4 e 5:")
        print("  AA:BB:CC:DD:EE:FF  ->  AA:BB:CC:00:00:FF")
        print("  AABBCCDDEEFF       ->  AABBCC0000FF")
        print("  hefesto_som_DDEEFF ->  hefesto_som_0000FF")
        print("\nSe o achado NÃO for endereço (hash, carimbo, UUID), acrescente o")
        print("caminho a EXCLUIR_CAMINHO neste arquivo, com o motivo escrito ao lado.")
        return 1

    print("OK: nenhum endereço de rádio real em arquivo versionado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
