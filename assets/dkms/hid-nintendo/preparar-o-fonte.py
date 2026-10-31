#!/usr/bin/env python3
"""Põe no lugar o fonte do kernel que roda: o de fábrica dele mais a série de `patch/`.

A ordem: o fonte conferido em `fonte-por-kernel/` (o cache); senão, o de fábrica do kernel,
achado na árvore do kernel, na fonte da distro ou no stable do kernel.org da versão que os
headers declaram, conferido pelo `srcversion` do módulo de fábrica, com a série aplicada sem
fuzz. O veredito vai ao `fonte-<kernel>.txt` da pasta do veredito.

Com `--exclusivo`, roda quando o DKMS lê o `dkms.conf` e imprime o `BUILD_EXCLUSIVE_KERNEL`:
vazio quando o fonte se preparou (guardado em `fonte-<kernel>.tar`), e um padrão que nenhum
kernel casa quando o de fábrica fica, para o DKMS pular com 77 e o `autoinstall` não reprovar
a instalação do kernel. Sem ele, é o `PRE_BUILD`: usa o guardado ou decide na hora.

    preparar-o-fonte.py [--exclusivo] <kernelver> <kernel_source_dir> [<pasta do veredito>]
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
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PULA = 77
NENHUM_KERNEL = "^/"
FALHA_VALE = 600
BEM = ("cache", "fabrica")
STABLE = "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/{caminho}?h={tag}"
INCLUDE_LOCAL = re.compile(r'^\s*#\s*include\s+"([^"/]+)"', re.M)
MAIS_PONTOS = 40
Leitor = Callable[[str], "bytes | None"]


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


def _versao(build: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", build))


def _series() -> list[tuple[str, list[Path]]]:
    rebases = sorted(
        (p for p in (AQUI / "fonte-por-kernel").glob("*/patch") if p.is_dir()),
        key=lambda p: _versao(p.parent.name),
        reverse=True,
    )
    return [
        (f"fonte-por-kernel/{p.parent.name}/patch/", sorted(p.glob("*.patch"))) for p in rebases
    ] + [("patch/", _serie())]


class NaoAplicaError(Exception):
    def __init__(self, patch: str, pedacos: int) -> None:
        super().__init__(patch)
        self.patch = patch
        self.pedacos = pedacos


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


def _do_cache(kver: str, modulo: str, destino: Path) -> str | None:
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
                shutil.copyfile(arquivo, destino / arquivo.name)
        origem = f"o fonte conferido de {build} no lugar"
    elif build in raiz:
        origem = f"o fonte da raiz serve a {build}"
    else:
        return None
    if main.is_file():
        shutil.copyfile(main, destino / "main.h")
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


def _pastas_do_include(caminho: str) -> list[str]:
    pasta = caminho.rsplit("/", 1)[0]
    return [pasta, pasta.rsplit("/", 1)[0]] if "/" in pasta else [pasta]


def _fecho(principal: str, ler: Leitor, faltou: list[str] | None = None) -> dict[str, bytes] | None:
    arquivos: dict[str, bytes] = {}

    def abrir(caminhos: list[str]) -> bool:
        for caminho in caminhos:
            if caminho in arquivos:
                return True
            conteudo = ler(caminho)
            if conteudo is None:
                continue
            arquivos[caminho] = conteudo
            return all(
                abrir([f"{p}/{nome}" for p in _pastas_do_include(caminho)])
                for nome in INCLUDE_LOCAL.findall(conteudo.decode("utf-8", errors="replace"))
            )
        if faltou is not None:
            faltou.append(caminhos[0])
        return False

    return arquivos if abrir([principal]) else None


def _da_arvore(raiz: Path) -> Leitor:
    def ler(caminho: str) -> bytes | None:
        arquivo = raiz / caminho
        return arquivo.read_bytes() if arquivo.is_file() else None

    return ler


def _do_tar(arquivo: str, pasta: str) -> Leitor:
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


def _do_stable(tag: str) -> Leitor:
    modelo = os.environ.get("HEFESTO_DKMS_STABLE_URL", STABLE)

    def ler(caminho: str) -> bytes | None:
        try:
            pedido = urllib.request.Request(
                modelo.format(caminho=caminho, tag=tag),
                headers={"User-Agent": "hefesto-dualsense4unix-dkms"},
            )
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                return bytes(resposta.read())
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                return None
            raise SemRedeError(str(erro)) from erro
        except FileNotFoundError:
            return None
        except (urllib.error.URLError, OSError, ValueError) as erro:
            raise SemRedeError(str(getattr(erro, "reason", erro))) from erro

    return ler


def _versao_do_kernel(texto: str) -> tuple[int, int, int] | None:
    achado = re.match(r"\s*(\d+)\.(\d+)(?:\.(\d+))?", texto)
    if not achado:
        return None
    return int(achado.group(1)), int(achado.group(2)), int(achado.group(3) or 0)


def _tag(versao: tuple[int, int, int]) -> str:
    maior, menor, ponto = versao
    return f"v{maior}.{menor}" if ponto == 0 else f"v{maior}.{menor}.{ponto}"


def _dos_headers(ksrc: str) -> tuple[int, int, int] | None:
    if not ksrc or not (Path(ksrc) / "Makefile").is_file():
        return None
    try:
        feito = subprocess.run(
            ["make", "-s", "-C", ksrc, "kernelversion"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return _versao_do_kernel(feito.stdout) if feito.returncode == 0 else None


def _tags(kver: str, ksrc: str, pontos: bool) -> list[str]:
    dos_headers = _dos_headers(ksrc)
    if not pontos:
        return [_tag(dos_headers)] if dos_headers else []
    tags = [_tag(dos_headers)] if dos_headers else []
    do_nome = _versao_do_kernel(kver)
    if do_nome:
        maior, menor, ponto = do_nome
        for z in range(ponto, ponto + MAIS_PONTOS):
            tag = _tag((maior, menor, z))
            if tag not in tags:
                tags.append(tag)
    return tags


def _candidatos(
    kver: str, ksrc: str, principal: str, tentei: list[str], pontos: bool
) -> Iterator[tuple[str, dict[str, bytes]]]:
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
    tags = _tags(kver, ksrc, pontos)
    if not tags:
        tentei.append(
            "o stable do kernel.org (os headers não dizem a versão exata, e sem o srcversion "
            "só a versão exata se confere)"
        )
    for tag in tags:
        faltou: list[str] = []
        try:
            arquivos = _fecho(principal, _do_stable(tag), faltou)
        except SemRedeError as erro:
            tentei.append(f"o stable {tag} (sem rede: {erro})")
            return
        if arquivos is None:
            if faltou and faltou[0] != principal:
                tentei.append(f"o stable {tag} (o {faltou[0]} que o fonte inclui não veio)")
            else:
                tentei.append(f"o stable {tag} (não existe)")
            return
        tentei.append(f"o stable {tag}")
        yield f"o stable {tag} do kernel.org", arquivos


def _md4_do_modpost(dados: bytes) -> str:
    def rol(valor: int, casas: int) -> int:
        valor &= 0xFFFFFFFF
        return ((valor << casas) | (valor >> (32 - casas))) & 0xFFFFFFFF

    def escolha(x: int, y: int, z: int) -> int:
        return (x & y) | (~x & z)

    def maioria(x: int, y: int, z: int) -> int:
        return (x & y) | (x & z) | (y & z)

    def paridade(x: int, y: int, z: int) -> int:
        return x ^ y ^ z

    rodadas: tuple[
        tuple[Callable[[int, int, int], int], int, Sequence[int], Sequence[int]], ...
    ] = (
        (escolha, 0, range(16), (3, 7, 11, 19)),
        (
            maioria,
            0x5A827999,
            (0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15),
            (3, 5, 9, 13),
        ),
        (
            paridade,
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
    pasta = next(iter(arquivos)).rsplit("/", 1)[0] if arquivos else ""
    return _md4_do_modpost(
        b"".join(
            _texto_do_modpost(conteudo)
            for caminho, conteudo in arquivos.items()
            if caminho.rsplit("/", 1)[0] == pasta
        )
    )[:23]


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


def _confere(
    ksrc: str, modulo: str, arquivos: dict[str, bytes], fabrica: Path, destino: Path
) -> bool:
    de_fabrica = _modinfo("srcversion", fabrica)
    if de_fabrica:
        return [srcversion(arquivos)] == de_fabrica
    with tempfile.TemporaryDirectory(dir=destino, prefix=".fabrica-") as tmp:
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
    serie: list[Path], arquivos: dict[str, bytes], destino: Path
) -> tuple[dict[str, bytes], list[str]]:
    notas: list[str] = []
    with tempfile.TemporaryDirectory(dir=destino, prefix=".serie-") as tmp:
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
            raise NaoAplicaError(
                patch.name, len(re.findall(r"^Hunk #\d+ FAILED", ensaio.stdout, re.M))
            )
        return {caminho: (arvore / caminho).read_bytes() for caminho in arquivos}, notas


def _principal() -> str:
    return next((c for c in _caminhos_da_serie(_serie()) if c.endswith(".c")), "")


def _do_kernel(kver: str, ksrc: str, modulo: str, destino: Path) -> str:
    principal = _principal()
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
        if not _confere(ksrc, modulo, arquivos, fabrica, destino):
            continue
        falhas: list[str] = []
        for rotulo, serie_daqui in _series():
            try:
                curados, notas = _aplicar(serie_daqui, arquivos, destino)
            except NaoAplicaError as erro:
                falhas.append(
                    f"na de {rotulo}, o {erro.patch} deixa {erro.pedacos or 'algum'} "
                    "pedaço(s) de fora"
                )
                continue
            for caminho, conteudo in curados.items():
                (destino / caminho.rsplit("/", 1)[-1]).write_bytes(conteudo)
            conferencia = (
                "pelo srcversion"
                if pontos
                else "pelos alias e parâmetros no stable da versão que os headers declaram, "
                "que o kernel não grava srcversion"
            )
            return (
                f"hefesto-{modulo}: o fonte de fábrica de {kver} é {origem} "
                f"(conferido {conferencia}), e a série de {rotulo} aplicou ({', '.join(notas)})"
            )
        raise VereditoError(
            "nao-aplica",
            f"hefesto-{modulo}: nenhuma série guardada aplica no de fábrica de {kver} "
            f"({origem}): {'; '.join(falhas)}; o de fábrica assume até a série ganhar o rebase "
            "deste kernel (o ritual está em patch/BASELINE)",
        )
    raise VereditoError(
        "sem-fonte",
        f"hefesto-{modulo}: não achei o fonte de fábrica de {kver} ({'; '.join(tentei)}); "
        "o de fábrica assume. Para construir o do Hefesto: instale a fonte do kernel da "
        "distro (linux-source) ou deixe a rede alcançar o git.kernel.org e rode o install de novo",
    )


def _chave(kver: str) -> str:
    principal = _principal()
    fabrica = (
        _modulo_de_fabrica(kver, principal.rsplit("/", 1)[0], _conf("BUILT_MODULE_NAME[0]"))
        if principal
        else None
    )
    if fabrica is None:
        return "sem-fabrica"
    dados = fabrica.stat()
    return f"{fabrica}:{dados.st_size}:{dados.st_mtime_ns}"


def _gravar(veredito: Path | None, kver: str, estado: str, frase: str, chave: str = "") -> None:
    print(frase, file=sys.stderr if estado not in BEM else sys.stdout)
    if veredito is None:
        return
    with contextlib.suppress(OSError):
        (veredito / f"fonte-{kver}.txt").write_text(
            f"{estado}\n{frase}\n{chave}\n", encoding="utf-8"
        )


def _lido(veredito: Path, kver: str) -> tuple[str, str, str, float]:
    arquivo = veredito / f"fonte-{kver}.txt"
    try:
        linhas = arquivo.read_text(encoding="utf-8").split("\n")
        idade = time.time() - arquivo.stat().st_mtime
    except OSError:
        return "", "", "", 0.0
    linhas += ["", "", ""]
    return linhas[0], linhas[1], linhas[2], idade


def _decidir(kver: str, ksrc: str, modulo: str, destino: Path) -> tuple[str, str]:
    do_cache = _do_cache(kver, modulo, destino)
    if do_cache:
        return "cache", do_cache
    try:
        return "fabrica", _do_kernel(kver, ksrc, modulo, destino)
    except VereditoError as motivo:
        return motivo.estado, motivo.frase


def _exclusivo(kver: str, ksrc: str, veredito: Path | None) -> str:
    modulo = _conf("BUILT_MODULE_NAME[0]")
    if not kver or not modulo or veredito is None or (veredito / kver).is_dir():
        return ""
    if not (Path(ksrc) / "Makefile").is_file():
        ksrc = str(_modulos_root() / kver / "build")
        if not (Path(ksrc) / "Makefile").is_file():
            return ""
    if not veredito.is_dir() or not os.access(veredito, os.W_OK):
        return ""
    chave = _chave(kver)
    guardado = veredito / f"fonte-{kver}.tar"
    estado, _frase, chave_lida, idade = _lido(veredito, kver)
    if chave_lida == chave and estado in BEM and guardado.is_file():
        return ""
    if chave_lida == chave and estado and estado not in BEM and idade < FALHA_VALE:
        return NENHUM_KERNEL
    with tempfile.TemporaryDirectory(dir=veredito, prefix=".fonte-") as tmp:
        with contextlib.redirect_stdout(sys.stderr):
            estado, frase = _decidir(kver, ksrc, modulo, Path(tmp))
            _gravar(veredito, kver, estado, frase, chave)
        if estado not in BEM:
            guardado.unlink(missing_ok=True)
            return NENHUM_KERNEL
        with tarfile.open(guardado, "w") as tar:
            for arquivo in sorted(Path(tmp).iterdir()):
                if arquivo.is_file() and not arquivo.name.startswith("."):
                    tar.add(arquivo, arcname=arquivo.name)
    return ""


def _do_guardado(veredito: Path | None, kver: str) -> bool:
    if veredito is None:
        return False
    estado, frase, chave_lida, _idade = _lido(veredito, kver)
    guardado = veredito / f"fonte-{kver}.tar"
    if estado not in BEM or chave_lida != _chave(kver) or not guardado.is_file():
        return False
    try:
        with tarfile.open(guardado) as tar:
            for info in tar:
                if not info.isfile() or "/" in info.name or info.name.startswith("."):
                    continue
                conteudo = tar.extractfile(info)
                if conteudo:
                    (AQUI / info.name).write_bytes(conteudo.read())
    except (tarfile.TarError, OSError):
        return False
    print(frase)
    return True


def main(argv: list[str]) -> int:
    exclusivo = bool(argv) and argv[0] == "--exclusivo"
    if exclusivo:
        argv = argv[1:]
    if len(argv) < 2:
        print(
            "uso: preparar-o-fonte.py [--exclusivo] <kernelver> <kernel_source_dir> "
            "[<pasta do veredito>]",
            file=sys.stderr,
        )
        return 2
    kver, ksrc = argv[0], argv[1]
    veredito = Path(argv[2]) if len(argv) > 2 and argv[2] else None
    if exclusivo:
        try:
            print(_exclusivo(kver, ksrc, veredito))
        except Exception as erro:
            print(f"preparar-o-fonte: {erro}", file=sys.stderr)
            print("")
        return 0
    modulo = _conf("BUILT_MODULE_NAME[0]")
    if not modulo:
        print("preparar-o-fonte: o dkms.conf não diz o BUILT_MODULE_NAME[0]", file=sys.stderr)
        return 1
    if _do_guardado(veredito, kver):
        return 0
    estado, frase = _decidir(kver, ksrc, modulo, AQUI)
    _gravar(veredito, kver, estado, frase, _chave(kver))
    if estado not in BEM:
        (AQUI / "Makefile").write_text(f"$(error {frase})\n", encoding="utf-8")
        return PULA
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
