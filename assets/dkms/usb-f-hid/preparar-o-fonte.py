#!/usr/bin/env python3
"""Põe no lugar o fonte do kernel que roda: o de fábrica dele mais a série de `patch/`.

O `PRE_BUILD` de cada pacote DKMS. A ordem: o fonte conferido em `fonte-por-kernel/` (o
cache); senão, o de fábrica do kernel, achado na árvore do kernel, na fonte da distro ou no
stable do kernel.org, conferido pelo `srcversion` do módulo de fábrica, com a série aplicada
sem fuzz. Quando o de fábrica fica, sai com 77 e o motivo vai ao `fonte-<kernel>.txt`.

    preparar-o-fonte.py <kernelver> <kernel_source_dir> [<pasta do veredito>]
"""

from __future__ import annotations

import contextlib
import glob
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PULA = 77
STABLE = "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/{caminho}?h={tag}"
INCLUDE_LOCAL = re.compile(r'^\s*#\s*include\s+"([^"/]+)"', re.M)
MAIS_PONTOS = 40


class VereditoError(Exception):
    def __init__(self, estado: str, frase: str) -> None:
        super().__init__(frase)
        self.estado = estado
        self.frase = frase


def _conf(chave: str) -> str:
    achado = re.search(rf'^{re.escape(chave)}="([^"]*)"', (AQUI / "dkms.conf").read_text(), re.M)
    return achado.group(1) if achado else ""


def _serie() -> list[Path]:
    return sorted((AQUI / "patch").glob("*.patch"))


def _caminhos_da_serie(serie: list[Path]) -> list[str]:
    caminhos: list[str] = []
    for patch in serie:
        for linha in patch.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("+++ b/"):
                caminho = linha[6:].split("\t")[0].strip()
                if caminho not in caminhos:
                    caminhos.append(caminho)
    return caminhos


def _build(kver: str) -> str:
    return kver.rsplit("-", 1)[0] if "-" in kver else kver


def _do_cache(kver: str, modulo: str) -> str | None:
    build = _build(kver)
    por_kernel = AQUI / "fonte-por-kernel"
    main = AQUI / "main-por-kernel" / f"main-{build}.h"
    if (AQUI / "main-por-kernel").is_dir() and not main.is_file():
        return None
    pasta = por_kernel / build
    raiz = (
        (por_kernel / "raiz.txt").read_text().split() if (por_kernel / "raiz.txt").is_file() else []
    )
    if pasta.is_dir():
        for arquivo in pasta.iterdir():
            if arquivo.is_file():
                shutil.copyfile(arquivo, AQUI / arquivo.name)
        origem = f"o fonte conferido de {build} no lugar"
    elif build in raiz:
        origem = f"o fonte da raiz serve a {build}"
    else:
        return None
    if main.is_file():
        shutil.copyfile(main, AQUI / "main.h")
    return f"hefesto-{modulo}: {origem}"


def _modulos_root() -> Path:
    return Path(os.environ.get("HEFESTO_DKMS_MODULES_ROOT", "/lib/modules"))


def _modulo_de_fabrica(kver: str, pasta: str, modulo: str) -> Path | None:
    for candidato in sorted((_modulos_root() / kver / "kernel" / pasta).glob(f"{modulo}.ko*")):
        return candidato
    return None


def _modinfo(campo: str, ko: Path) -> list[str]:
    feito = subprocess.run(
        ["modinfo", "-F", campo, str(ko)], capture_output=True, text=True, check=False
    )
    return [linha.strip() for linha in feito.stdout.splitlines() if linha.strip()]


def _fecho(principal: str, ler) -> dict[str, bytes] | None:
    pasta = principal.rsplit("/", 1)[0]
    arquivos: dict[str, bytes] = {}

    def abrir(caminho: str) -> bool:
        if caminho in arquivos:
            return True
        conteudo = ler(caminho)
        if conteudo is None:
            return False
        arquivos[caminho] = conteudo
        return all(
            abrir(f"{pasta}/{nome}")
            for nome in INCLUDE_LOCAL.findall(conteudo.decode("utf-8", errors="replace"))
        )

    return arquivos if abrir(principal) else None


def _da_arvore(raiz: Path):
    def ler(caminho: str) -> bytes | None:
        arquivo = raiz / caminho
        return arquivo.read_bytes() if arquivo.is_file() else None

    return ler


def _do_tar(arquivo: str, pasta: str):
    membros: dict[str, bytes] = {}
    lido: list[bool] = []

    def ler(caminho: str) -> bytes | None:
        if not lido:
            lido.append(True)
            try:
                with tarfile.open(arquivo) as tar:
                    for info in tar:
                        relativo = info.name.split("/", 1)[-1]
                        if info.isfile() and relativo.startswith(f"{pasta}/"):
                            conteudo = tar.extractfile(info)
                            if conteudo:
                                membros[relativo] = conteudo.read()
            except (tarfile.TarError, OSError):
                pass
        return membros.get(caminho)

    return ler


class SemRedeError(Exception):
    pass


def _do_stable(tag: str):
    modelo = os.environ.get("HEFESTO_DKMS_STABLE_URL", STABLE)

    def ler(caminho: str) -> bytes | None:
        try:
            pedido = urllib.request.Request(
                modelo.format(caminho=caminho, tag=tag),
                headers={"User-Agent": "hefesto-dualsense4unix-dkms"},
            )
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                return None
            raise SemRedeError(str(erro)) from erro
        except FileNotFoundError:
            return None
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise SemRedeError(str(getattr(erro, "reason", erro))) from erro

    return ler


def _tags(kver: str) -> Iterator[str]:
    achado = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", kver)
    if not achado:
        return
    maior, menor, ponto = achado.group(1), achado.group(2), int(achado.group(3) or 0)
    for z in range(ponto, ponto + MAIS_PONTOS):
        yield f"v{maior}.{menor}" if z == 0 else f"v{maior}.{menor}.{z}"


def _candidatos(kver: str, ksrc: str, principal: str, tentei: list[str], pontos: bool):
    for raiz in (Path(ksrc), _modulos_root() / kver / "source"):
        arquivos = _fecho(principal, _da_arvore(raiz))
        tentei.append(f"a árvore em {raiz}")
        if arquivos:
            yield f"a árvore em {raiz}", arquivos
    distro = os.environ.get(
        "HEFESTO_DKMS_FONTE_DA_DISTRO", "/usr/src/linux-source-*/linux-source-*.tar.*"
    )
    for tarball in sorted(glob.glob(distro), reverse=True):
        tentei.append(f"a fonte da distro em {tarball}")
        arquivos = _fecho(principal, _do_tar(tarball, principal.rsplit("/", 1)[0]))
        if arquivos:
            yield f"a fonte da distro em {tarball}", arquivos
    for tag in _tags(kver):
        try:
            arquivos = _fecho(principal, _do_stable(tag))
        except SemRedeError as erro:
            tentei.append(f"o stable {tag} (sem rede: {erro})")
            return
        if arquivos is None:
            tentei.append(f"o stable {tag} (não existe)")
            return
        tentei.append(f"o stable {tag}")
        yield f"o stable {tag} do kernel.org", arquivos
        if not pontos:
            return


def _md4_do_modpost(dados: bytes) -> str:
    def rol(valor: int, casas: int) -> int:
        valor &= 0xFFFFFFFF
        return ((valor << casas) | (valor >> (32 - casas))) & 0xFFFFFFFF

    rodadas = (
        (lambda x, y, z: (x & y) | (~x & z), 0, range(16), (3, 7, 11, 19)),
        (
            lambda x, y, z: (x & y) | (x & z) | (y & z),
            0x5A827999,
            (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15),
            (3, 5, 9, 13),
        ),
        (
            lambda x, y, z: x ^ y ^ z,
            0x6ED9EBA1,
            (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15),
            (3, 9, 11, 15),
        ),
    )
    bits = len(dados) * 8
    mensagem = dados + b"\x80" + b"\x00" * ((55 - len(dados)) % 64) + b"\x00" * 8
    estado = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
    for inicio in range(0, len(mensagem), 64):
        palavras = list(struct.unpack(">16I", mensagem[inicio : inicio + 64]))
        if inicio + 64 == len(mensagem):
            palavras[14], palavras[15] = bits & 0xFFFFFFFF, (bits >> 32) & 0xFFFFFFFF
        h = list(estado)
        for funcao, constante, ordem, casas in rodadas:
            for passo, indice in enumerate(ordem):
                alvo = (4 - passo % 4) % 4
                b, c, d = h[(alvo + 1) % 4], h[(alvo + 2) % 4], h[(alvo + 3) % 4]
                h[alvo] = rol(
                    h[alvo] + funcao(b, c, d) + palavras[indice] + constante, casas[passo % 4]
                )
        estado = [(a + b) & 0xFFFFFFFF for a, b in zip(estado, h, strict=True)]
    return "".join(f"{struct.unpack('>I', struct.pack('<I', p))[0]:08X}" for p in estado)


def _texto_do_modpost(conteudo: bytes) -> bytes:
    saida = bytearray()
    i, fim = 0, len(conteudo)
    while i < fim:
        letra = conteudo[i]
        if letra == 0x5C and i + 1 < fim and conteudo[i + 1] == 0x0A:
            i += 2
        elif letra in b" \t\n\v\f\r":
            i += 1
        elif letra == 0x22:
            j = i + 1
            while j < fim and not (conteudo[j] == 0x22 and conteudo[j - 1] != 0x5C):
                j += 1
            saida += conteudo[i : j + 1]
            i = j + 1
        elif letra == 0x2F and i + 1 < fim and conteudo[i + 1] == 0x2A:
            j = i + 2
            while j < fim and not (conteudo[j - 1] == 0x2A and conteudo[j] == 0x2F):
                j += 1
            i = j + 1
        else:
            saida.append(letra)
            i += 1
    return bytes(saida)


def srcversion(arquivos: dict[str, bytes]) -> str:
    return _md4_do_modpost(b"".join(_texto_do_modpost(c) for c in arquivos.values()))[:23]


def _compilar(ksrc: str, arquivos: dict[str, bytes], pasta: Path) -> None:
    shutil.copyfile(AQUI / "Makefile", pasta / "Makefile")
    for caminho, conteudo in arquivos.items():
        (pasta / caminho.rsplit("/", 1)[-1]).write_bytes(conteudo)
    subprocess.run(
        ["make", "-C", ksrc, f"M={pasta}", "modules"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _confere(ksrc: str, modulo: str, arquivos: dict[str, bytes], fabrica: Path) -> bool:
    de_fabrica = _modinfo("srcversion", fabrica)
    if de_fabrica:
        return [srcversion(arquivos)] == de_fabrica
    with tempfile.TemporaryDirectory(dir=AQUI, prefix=".fabrica-") as tmp:
        _compilar(ksrc, arquivos, Path(tmp))
        ko = next(
            (
                k
                for k in (Path(tmp) / f"{modulo.replace('-', '_')}.ko", Path(tmp) / f"{modulo}.ko")
                if k.is_file()
            ),
            None,
        )
        return ko is not None and all(
            sorted(_modinfo(campo, ko)) == sorted(_modinfo(campo, fabrica))
            for campo in ("alias", "parm")
        )


def _aplicar(
    serie: list[Path], arquivos: dict[str, bytes], origem: str, kver: str, modulo: str
) -> tuple[dict[str, bytes], list[str]]:
    notas: list[str] = []
    with tempfile.TemporaryDirectory(dir=AQUI, prefix=".serie-") as tmp:
        arvore = Path(tmp)
        for caminho, conteudo in arquivos.items():
            (arvore / caminho).parent.mkdir(parents=True, exist_ok=True)
            (arvore / caminho).write_bytes(conteudo)
        for patch in serie:
            base = [
                "patch",
                "-p1",
                "-F0",
                "--batch",
                "--no-backup-if-mismatch",
                "-d",
                str(arvore),
                "-i",
                str(patch),
            ]
            ensaio = subprocess.run(
                [*base, "--dry-run", "--forward"], capture_output=True, text=True, check=False
            )
            if ensaio.returncode == 0:
                subprocess.run(base, capture_output=True, text=True, check=True)
                notas.append(f"{patch.name[:4]} entra")
                continue
            desfeito = subprocess.run(
                [*base, "--dry-run", "-R"], capture_output=True, text=True, check=False
            )
            if desfeito.returncode == 0:
                notas.append(f"{patch.name[:4]} já está no kernel")
                continue
            pedacos = len(re.findall(r"^Hunk #\d+ FAILED", ensaio.stdout, re.M))
            raise VereditoError(
                "nao-aplica",
                f"hefesto-{modulo}: a série de patch/ não aplica no de fábrica de {kver} "
                f"({origem}): {patch.name} deixa {pedacos or 'algum'} pedaço(s) de fora; "
                "o de fábrica assume até a série ganhar o rebase deste kernel "
                "(o ritual está em patch/BASELINE)",
            )
        return {caminho: (arvore / caminho).read_bytes() for caminho in arquivos}, notas


def _do_kernel(kver: str, ksrc: str, modulo: str) -> str:
    serie = _serie()
    caminhos = _caminhos_da_serie(serie)
    principal = next((c for c in caminhos if c.endswith(".c")), "")
    if not principal:
        raise VereditoError(
            "sem-serie", f"hefesto-{modulo}: a série de patch/ não diz qual .c do kernel cura"
        )
    pasta = principal.rsplit("/", 1)[0]
    fabrica = _modulo_de_fabrica(kver, pasta, modulo)
    if fabrica is None:
        raise VereditoError(
            "sem-fabrica",
            f"hefesto-{modulo}: o kernel {kver} não traz o {modulo} de fábrica em {pasta}, "
            "e sem ele não há o que conferir nem o que substituir",
        )
    pontos = bool(_modinfo("srcversion", fabrica))
    tentei: list[str] = []
    vistos: set[str] = set()
    for origem, arquivos in _candidatos(kver, ksrc, principal, tentei, pontos):
        assinatura = hashlib.sha256(b"".join(sorted(arquivos.values()))).hexdigest()
        if assinatura in vistos:
            continue
        vistos.add(assinatura)
        if not _confere(ksrc, modulo, arquivos, fabrica):
            continue
        curados, notas = _aplicar(serie, arquivos, origem, kver, modulo)
        for caminho, conteudo in curados.items():
            (AQUI / caminho.rsplit("/", 1)[-1]).write_bytes(conteudo)
        conferencia = (
            "pelo srcversion"
            if pontos
            else "pelos alias e parâmetros, que o kernel não grava srcversion"
        )
        return (
            f"hefesto-{modulo}: o de fábrica de {kver} veio de {origem} (conferido {conferencia}), "
            f"e a série de patch/ aplicou ({', '.join(notas)})"
        )
    raise VereditoError(
        "sem-fonte",
        f"hefesto-{modulo}: não achei o fonte de fábrica de {kver} ({'; '.join(tentei)}); "
        "o de fábrica assume. Para construir o do Hefesto: instale a fonte do kernel da "
        "distro (linux-source) ou deixe a rede alcançar o git.kernel.org e rode o install de novo",
    )


def _gravar(veredito: Path | None, kver: str, estado: str, frase: str) -> None:
    print(frase, file=sys.stderr if estado not in ("cache", "fabrica") else sys.stdout)
    if veredito is None:
        return
    with contextlib.suppress(OSError):
        (veredito / f"fonte-{kver}.txt").write_text(f"{estado}\n{frase}\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "uso: preparar-o-fonte.py <kernelver> <kernel_source_dir> [<pasta do veredito>]",
            file=sys.stderr,
        )
        return 2
    kver, ksrc = argv[0], argv[1]
    veredito = Path(argv[2]) if len(argv) > 2 and argv[2] else None
    modulo = _conf("BUILT_MODULE_NAME[0]")
    if not modulo:
        print("preparar-o-fonte: o dkms.conf não diz o BUILT_MODULE_NAME[0]", file=sys.stderr)
        return 1
    do_cache = _do_cache(kver, modulo)
    if do_cache:
        _gravar(veredito, kver, "cache", do_cache)
        return 0
    try:
        _gravar(veredito, kver, "fabrica", _do_kernel(kver, ksrc, modulo))
    except VereditoError as motivo:
        _gravar(veredito, kver, motivo.estado, motivo.frase)
        (AQUI / "Makefile").write_text(f"$(error {motivo.frase})\n", encoding="utf-8")
        return PULA
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
